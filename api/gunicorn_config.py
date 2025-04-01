from __future__ import annotations

import ctypes
import socket
import struct
import sys
import time
from multiprocessing import Value
from threading import Event, Thread

from gunicorn.http import message, wsgi
from gunicorn.workers import gthread

from common import stats
from utils import log

log.configure()

# https://github.com/benoitc/gunicorn/blob/master/examples/example_config.py
# disable to avoid the global referencing issue across process boundaries
# preload_app = True
bind = "0.0.0.0:5000"
# tune this later if needed
# backlog = 2048

workers = 8
# 2-4 * num_cores as recommended
threads = 8
# nginx timeout is 60s for now -
# gunicorn should kill workers with enough time to allow a request to retry.
# this seldom happens after the lost connection to mysql issue fix, tracked by worker_abort metric
timeout = 35
# keep in sync with nginx side setting
# keepalive = 5

# time interval setting for emitting backlog metric
BACKLOG_METRIC_INTERVAL = 5
monitor_stop_event = Event()

# Server hooks


def on_starting(server):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    server.live_worker_count = Value(ctypes.c_uint, 0)
    server.log.debug("[gunicorn] server is starting")


def when_ready(server):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    server.log.debug(
        "[gunicorn] server is almost ready, starting backlog monitor daemon..."
    )
    monitoring_daemon = BacklogQueueMonitor(server, monitor_stop_event)
    monitoring_daemon.start()
    server.log.info("[gunicorn] server is ready")


def on_exit(server):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    server.log.info("[gunicorn] server is exiting...")
    monitor_stop_event.set()


def pre_fork(server, worker):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # add sleep logic to smooth out the resource contentions
    if server.live_worker_count.value >= server.num_workers:
        server.live_worker_count.value -= server.num_workers
    server.live_worker_count.value += 1
    if server.live_worker_count.value > 1:
        max_sleep_time = (
            2.8
            if server.live_worker_count.value > 2
            else server.live_worker_count.value
        )
        time.sleep(max_sleep_time)

    worker.busy = Value(ctypes.c_uint, 0)
    worker.log.debug("[gunicorn] worker pre_fork event")


def post_fork(server, worker):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Ensure that each worker process has its own SDK state
    from maven import feature_flags

    feature_flags.initialize()


def pre_request(worker: gthread.ThreadWorker, req: message.Request) -> None:
    worker.busy.value += 1


def post_request(
    worker: gthread.ThreadWorker,
    req: message.Request,
    environ: dict[str, str],
    resp: wsgi.Response,
) -> None:
    if worker.busy.value > 0:
        worker.busy.value -= 1


def post_worker_init(worker):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name="mono.gunicorn.worker_init",
        pod_name=stats.PodNames.CORE_SERVICES,
    )
    worker.log.info("[gunicorn] worker post_init event")


def worker_int(worker):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name="mono.gunicorn.worker_int",
        pod_name=stats.PodNames.CORE_SERVICES,
    )
    worker.log.info("[gunicorn] worker interrupt event")


def worker_abort(worker):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name="mono.gunicorn.worker_abort",
        pod_name=stats.PodNames.CORE_SERVICES,
    )
    worker.log.info(
        "[gunicorn] worker abort event, this generally indicates a worker timeout"
    )


def worker_exit(server, worker):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name="mono.gunicorn.worker_exit",
        pod_name=stats.PodNames.CORE_SERVICES,
    )
    worker.log.info("[gunicorn] worker exit event")


class BacklogQueueMonitor(Thread):
    # https://gist.github.com/robotadam/9c1577ba05490960504eddd9037f2f9c
    def __init__(self, server, monitor_stop_event: Event):  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        super().__init__()
        self.server = server
        self.monitor_stop_event = monitor_stop_event
        self.daemon = True

    def run(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.server.log.info(
            f"[gunicorn] started BacklogQueueMonitor with interval {BACKLOG_METRIC_INTERVAL}"
        )
        while True:
            stats.gauge(
                metric_name="mono.gunicorn.num_running_workers",
                metric_value=self.server.num_workers,
                pod_name=stats.PodNames.CORE_SERVICES,
            )
            num_busy_workers = sum(
                worker.busy.value
                for worker in self.server.WORKERS.values()
                # put a cap to avoid potential noises
                if worker.busy.value and 0 < worker.busy.value < 1000
            )
            stats.gauge(
                metric_name="mono.gunicorn.num_busy_workers",
                metric_value=num_busy_workers,
                pod_name=stats.PodNames.CORE_SERVICES,
            )
            backlog = self.get_backlog()
            # number of pending requests in the queue
            stats.gauge(
                metric_name="mono.gunicorn.backlog",
                metric_value=backlog or 0,
                pod_name=stats.PodNames.CORE_SERVICES,
            )

            self.monitor_stop_event.wait(timeout=BACKLOG_METRIC_INTERVAL)
            if self.monitor_stop_event.is_set():
                self.monitor_stop_event.clear()
                if not sys.platform == "linux":
                    self.server.log.debug(
                        "[gunicorn] non-linux platform, no backlog metric available"
                    )
                self.server.log.info(
                    "[gunicorn] stop signal received, BacklogQueueMonitor shuts down"
                )
                return

    def get_backlog(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Get the number of connections waiting to be accepted by a server"""
        if not sys.platform == "linux":
            return None
        total = 0
        for listener in self.server.LISTENERS:
            if not listener.sock:
                continue

            # tcp_info struct from include/uapi/linux/tcp.h
            fmt = "B" * 8 + "I" * 24
            try:
                tcp_info_struct = listener.sock.getsockopt(
                    socket.IPPROTO_TCP, socket.TCP_INFO, 104
                )
                # 12 is tcpi_unacked
                total += struct.unpack(fmt, tcp_info_struct)[12]
            except AttributeError:
                pass

        return total
