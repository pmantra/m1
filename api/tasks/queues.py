from __future__ import annotations

import signal
import time
import uuid
from typing import Any, Tuple

import sqlalchemy
from maven import feature_flags
from redis.exceptions import RedisError
from rq import Queue, Retry, Worker
from rq.job import Job, requeue_job
from rq.utils import utcnow
from rq.worker import StopRequested
from sqlalchemy import create_engine

import configuration
from app import create_app
from common import stats
from tasks.job_callbacks import (
    get_job_func_name,
    on_failure_callback_wrapper,
    on_stopped_callback_wrapper,
    on_success_callback_wrapper,
    on_work_horse_killed_handler,
)
from tasks.owner_utils import get_pod_name, inject_owner_count_metric
from tasks.worker_utils import ensure_dependency_readiness
from utils.cache import redis_client
from utils.constants import CronJobName
from utils.launchdarkly import should_job_run_in_airflow
from utils.log import logger
from utils.service_owner_mapper import (
    CALLER_TAG,
    SERVICE_NS_TAG,
    TEAM_NS_TAG,
    TRACKING_ID,
)

logger = logger(__name__)
# set to 10 minutes
_DEFAULT_JOB_TIMEOUT = 10 * 60
_MAX_HEALTH_PROBE_RETRY = 10
_DB_CONNECTION_DETECTION_RETRY_TIMES = 5
_JOBS_NEED_WORKER_STATUS_DETECTION = ("send_to_zendesk",)
_DEFAULT_REDUCED_SAMPLE_RATE = 0.1
_CRON_JOB_NAME = "cron_job_name"

REDIS_EXCEPTION_SCHEDULING_FN_ERROR_COUNT = (
    "api.tasks.queues.schedule_fn.redis_exception.count"
)
GENERIC_EXCEPTION_SCHEDULING_FN_ERROR_COUNT = (
    "api.tasks.queues.schedule_fn.generic_exception.count"
)


def work(queues):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    worker = MavenWorker(
        queues,
        # use the new default memory store instance
        connection=redis_client(),
        log_job_description=False,
        default_worker_ttl=300,
        work_horse_killed_handler=on_work_horse_killed_handler,
    )
    worker.work(with_scheduler=True)


class MavenWorker(Worker):
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        conf = configuration.get_api_config()
        self.engine: sqlalchemy.engine.Engine = create_engine(
            conf.common.sqlalchemy.databases.default_url,
        )
        super().__init__(*args, **kwargs)

    def check_for_suspension(self, burst: bool):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        time_now = utcnow()
        is_healthy = ensure_dependency_readiness(
            max_retry_limit=_MAX_HEALTH_PROBE_RETRY
        )
        if not is_healthy:
            # metric is added in the dependency check
            logger.warning("Maven worker health check failed, quitting...")  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "warning"
            # at this point, the worker should have no pending jobs
            self._shutdown_requested_date = time_now
            self.request_force_stop(signum=signal.SIGTERM, frame=None)

        return super().check_for_suspension(burst)

    def handle_job_failure(self, job, queue, started_job_registry=None, exc_string=""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Only for debugging purpose. Will remove later
        job_is_stopped = self._stopped_job_id == job.id
        retry = job.retries_left and job.retries_left > 0 and not job_is_stopped

        _, job_func_name = get_job_func_name(job)
        logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
            "Before handle job failure",
            job_name=job_func_name,
            job_id=job.id,
            job_tracking_id=get_job_tracking_id(job),
            stopped_job_id=self._stopped_job_id,
            retries_left=job.retries_left,
            retry_intervals=job.retry_intervals,
            exc_string=exc_string,
            job_is_stopped=job_is_stopped,
            job_status=job.get_status(),
            retry=retry,
        )

        result = super().handle_job_failure(
            job, queue, started_job_registry, exc_string
        )

        logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
            "After handle job failure",
            job_name=job_func_name,
            job_id=job.id,
            job_tracking_id=get_job_tracking_id(job),
            stopped_job_id=self._stopped_job_id,
            retries_left=job.retries_left,
            retry_intervals=job.retry_intervals,
            exc_string=exc_string,
            job_is_stopped=job_is_stopped,
            job_status=job.get_status(),
            retry=retry,
        )

        return result

    def is_stop_requested(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self._stop_requested

    def do_status_detection(self, job, job_name_check=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, job_func_name = get_job_func_name(job)
        if job_name_check:
            if not list(
                filter(
                    lambda job_to_check: job_to_check in job_func_name,
                    _JOBS_NEED_WORKER_STATUS_DETECTION,
                )
            ):
                return False

        job_tracking_id = get_job_tracking_id(job)
        retry = 0

        while retry < _DB_CONNECTION_DETECTION_RETRY_TIMES:
            try:
                with self.engine.connect() as conn:
                    db_ok = bool(conn.scalar("SELECT 1 as ok"))
            except Exception as e:
                logger.warn(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "warn"
                    "Error in executing the detection query",
                    job_id=job.id,
                    job_tracking_id=job_tracking_id,
                    job_name=job_func_name,
                    retry=retry,
                    exception_message=str(e),
                )
                db_ok = False

            logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
                "DB connection is good during performing job ?",
                db_ok=db_ok,
                job_id=job.id,
                job_tracking_id=job_tracking_id,
                job_name=job_func_name,
                retry=retry,
            )

            if db_ok:
                break
            else:
                retry = retry + 1
                time.sleep(1)

        if retry == _DB_CONNECTION_DETECTION_RETRY_TIMES:
            logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                "DB connection failed. Add the job back to the queue",
                job_id=job.id,
                job_tracking_id=job_tracking_id,
                job_name=job_func_name,
            )
            try:
                # Have to fail the job so that requeue can be successful according to RQ implementation
                job.failed_job_registry.add(job)
                requeue_job(job.id, self.connection)
                self.request_stop(signal.SIGTERM, frame=None)
            except StopRequested:
                # expect to see StopRequested exception from request_stop
                pass
            except Exception as e:
                logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                    "Error during requeue when DB connection gets lost",
                    job_id=job.id,
                    job_tracking_id=job_tracking_id,
                    job_name=job_func_name,
                    exception_type=e.__class__.__name__,
                    exception_message=str(e),
                )
                raise e
            raise Exception("DB connection failed")
        elif self.is_stop_requested():
            logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                "Worker has been stopped. Add the job back to the queue",
                job_id=job.id,
                job_tracking_id=job_tracking_id,
                job_name=job_func_name,
            )
            try:
                # Have to fail the job so that requeue can be successful according to RQ implementation
                job.failed_job_registry.add(job)
                requeue_job(job.id, self.connection)
            except Exception as e:
                logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                    "Error during requeue when worker has been stopped",
                    job_id=job.id,
                    job_tracking_id=job_tracking_id,
                    job_name=job_func_name,
                    exception_type=e.__class__.__name__,
                    exception_message=str(e),
                )
                raise e
            raise Exception("Worker has been stopped")
        return True

    def prepare_job_execution(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, _job: "Job", remove_from_intermediate_queue: bool = False
    ):
        _, job_func_name = get_job_func_name(_job)
        try:
            return super().prepare_job_execution(_job, remove_from_intermediate_queue)
        except Exception as e:
            logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                f"RQ worker has issues to prepare_job_execution with exception: {e}",
                job_id=_job.id,
                job_name=job_func_name,
            )
            # will create an alert
            # this is a severe alert and need to be investigated
            inject_owner_count_metric(
                metric_name="mono.rq_tasks.prepare_job_execution.error",
                team_ns="core_services",
            )
            # re-raise for the RQ framework to properly handle worker and job status
            raise e

    def execute_job(self, _job: "Job", queue: "Queue"):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            return super().execute_job(_job, queue)
        except Exception as e:
            # in most cases, this indicates a bigger serializer issue for job data
            logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                f"RQ worker has issues to execute_job with exception: {e}",
                job_id=_job.id,
            )
            # will create an alert
            # this is a severe alert and need to be investigated
            inject_owner_count_metric(
                metric_name="mono.rq_tasks.execute_job.error",
                team_ns="core_services",
            )
            # re-raise for the RQ framework to properly handle worker and job status
            raise e

    def perform_job(self, _job, queue):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _, job_func_name = get_job_func_name(_job)
        try:
            # Since RQ makes use of process forking to perform jobs in a 'work
            # horse' process, the feature flags SDK must be initialized explicitly:
            # https://gitlab.com/maven-clinic/packages/maven-sdk-feature-flags-python#auto-initialize
            feature_flags.initialize()
            self.do_status_detection(_job, job_name_check=False)
            application = create_app(task_instance=True)
            service_ns = _job.meta.get(SERVICE_NS_TAG, None) if _job.meta else None
            team_ns = _job.meta.get(TEAM_NS_TAG, None) if _job.meta else None
            caller = _job.meta.get(CALLER_TAG, None) if _job.meta else None
            default_tags = _job.meta.get("default_tags", []) if _job.meta else []
            with application.app_context():
                tags = [
                    f"task_name:{job_func_name}",
                    f"{SERVICE_NS_TAG}:{service_ns}",
                    f"{TEAM_NS_TAG}:{team_ns}",
                    f"{CALLER_TAG}:{caller}",
                    *default_tags,
                ]

                # we rely on metrics but re-enable this until the new logic is stable
                logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
                    "Starting job in RQ worker",
                    job_name=job_func_name,
                    team_ns=team_ns or "None",
                    service_ns=service_ns or "None",
                    caller=caller,
                    job_id=_job.id,
                    job_tracking_id=get_job_tracking_id(_job),
                )
                with stats.timed(
                    metric_name="mono.rq_tasks.duration",
                    pod_name=get_pod_name(team_ns),  # type: ignore[arg-type] # Argument "pod_name" to "timed" has incompatible type "str"; expected "PodNames"
                    tags=tags,
                    # this metric is mostly to show the trend
                    # sampling to reduce costs
                    sample_rate=_DEFAULT_REDUCED_SAMPLE_RATE,
                ):
                    return super().perform_job(_job, queue)
        except Exception as e:
            logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                f"RQ worker has issues to perform_job with exception: {e}",
                job_id=_job.id,
                job_name=job_func_name,
            )

            # will create an alert
            # this is a severe alert and need to be investigated
            inject_owner_count_metric(
                metric_name="mono.rq_tasks.perform_job.error",
                team_ns="core_services",
            )
            # re-raise for the RQ framework to properly handle worker and job status
            raise e
        finally:
            feature_flags.close()


def get_job_tracking_id(rq_job: Job):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return rq_job.meta.get(TRACKING_ID) if rq_job.meta else None


def set_task_service_name(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    name = getattr(func, "__module__", None)
    if name is not None:
        try:
            name = name[name.rindex(".") + 1 :]
        except ValueError:
            pass
        name = name.replace("_", "-")
        func.service_name = f"worker-{name}"


def get_task_service_name(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return getattr(func, "service_name", "worker-unknown")


def get_queue(name="default", connection=None, warning_threshold=100):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return Queue(
        name=name,
        # NOTE: during the migration period use the following workaround for checking the original queue details
        # connection = redis_client()
        # get_queue(name="<queue_name>", connection=connection)
        connection=connection or redis_client(),
        # if not set, the default timeout is 10 minutes
        default_timeout=_DEFAULT_JOB_TIMEOUT,
    )


def get_queue_host(queue: Queue) -> str:
    try:
        if queue.connection is None:
            return "Unknown"

        connection_kwargs = queue.connection.get_connection_kwargs()
        return connection_kwargs.get("host", "Unknown")
    except Exception:
        return "Unknown"


_TRACE_HEADERS = "trace_headers"


def job(func_or_queue="default", **jobargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    via https://github.com/mattupstate/flask-rq/blob/master/flask_rq.py
    """

    if callable(func_or_queue):
        func = func_or_queue
        queue = "default"
    else:
        func = None
        queue = func_or_queue

    def wrapper(fn):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        set_task_service_name(fn)
        job_team_ns = jobargs.get(TEAM_NS_TAG, None)
        job_service_ns = jobargs.get(SERVICE_NS_TAG, None)
        job_caller = jobargs.get(CALLER_TAG, None)

        def delay(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            cron_job_name: CronJobName = kwargs.pop(_CRON_JOB_NAME, None)
            if cron_job_name is not None:
                should_enqueue = not should_job_run_in_airflow(cron_job_name)
                if not should_enqueue:
                    logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
                        f"Cron job {cron_job_name} is not going to be scheduled in RQ"
                    )
                    return
                else:
                    logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
                        f"Cron job {cron_job_name} is going to be scheduled in RQ"
                    )
            default_tags = [f"queue:{str(queue)}"]
            service_ns = kwargs.pop(SERVICE_NS_TAG, job_service_ns)
            team_ns = kwargs.pop(TEAM_NS_TAG, job_team_ns)
            caller = kwargs.pop(CALLER_TAG, job_caller)
            meta = kwargs.pop("meta", {})
            meta[SERVICE_NS_TAG] = service_ns
            meta[TEAM_NS_TAG] = team_ns
            meta[CALLER_TAG] = caller
            meta["default_tags"] = default_tags

            kwargs.setdefault("failure_ttl", 3600)
            # add on_success/on_failure callback
            # TODO: add on_timeout callback when upgrade RQ to the latest version that supports the interface
            # TODO: add on_stopped callback
            original_on_success_callback = kwargs.pop("on_success", None)
            meta["original_on_success_callback"] = original_on_success_callback
            kwargs.setdefault("on_success", on_success_callback_wrapper)
            original_on_failure_callback = kwargs.pop("on_failure", None)
            meta["original_on_failure_callback"] = original_on_failure_callback
            kwargs.setdefault("on_failure", on_failure_callback_wrapper)
            original_on_stopped_callback = kwargs.pop("on_stopped", None)
            meta["original_on_stopped_callback"] = original_on_stopped_callback
            kwargs.setdefault("on_stopped", on_stopped_callback_wrapper)
            if not meta.get(TRACKING_ID):
                meta[TRACKING_ID] = str(uuid.uuid4())

            kwargs.setdefault("meta", meta)

            q = _queues[queue]
            queue_host = get_queue_host(q)

            inject_owner_count_metric(
                metric_name="mono.rq.en_queue",
                func=fn,
                tags=default_tags,
                service_ns=service_ns,
                team_ns=team_ns,
                caller=caller,
                queue_host=queue_host,
            )

            try:
                return q.enqueue(fn, *args, **kwargs)
            except Exception as e:
                # in most cases, this indicates a bigger serializer issue for job parameter data
                logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                    # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                    f"RQ worker has issues to enqueue the job with exception: {e}",
                    exc_info=e,
                    job_name=func.__name__,
                )
                # this is considered as a failure to alert the owner team for job data/logic issues
                inject_owner_count_metric(
                    metric_name="mono.rq_tasks.job_failure",
                    func=fn,
                    tags=default_tags,
                    service_ns=service_ns,
                    team_ns=team_ns,
                    caller=caller,
                    queue_host=queue_host,
                )
                # re-throw so people should be forced to update and fix the issue
                raise e

        fn.delay = delay
        return fn

    if func is not None:
        return wrapper(func)

    return wrapper


def default_backoff_func(tries):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    backoff_delay = 0
    if tries >= 1:
        backoff_delay = 1.5**tries
    return int(backoff_delay)


def retryable_job(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    func_or_queue="default",
    retry_limit=10,
    backoff_func=default_backoff_func,
    traced_parameters: Tuple[str, ...] = (),
    **jobargs,
):
    """retryable_job allows a python function to be executed by a background worker with some configurable retry behavior.

    When Retryable Jobs backoff for a retry attempt they synchronously block the worker from consuming other jobs on the queue.
    In the future we could use multiple queues, slower polling, or multiple workers but for now just know
    in the event of a failure the backoff will block the queue processing.

    Args:
        func_or_queue: string queue name or the function to turn into a retryable job
        retry_limit: the number of retry attempts before the job is moved to the failure queue (default: 10)
        backoff_func: a custom backoff method to delay the next execution, this backoff_func will be called with the attempt number starting at 0

    Examples:
        @retryable_job("default")
        def default_task():
            # do some work here or raise an exception

        default_task.delay()

        def flat_backoff(tries):
            backoff_delay = 0
            if tries >= 1:
                backoff_delay = 5
            return int(backoff_delay)

        @retryable_job("default", backoff_func=flat_backoff)
        def flat_backoff_task():
            # do some work here or raise an exception

        flat_backoff_task.delay()

        def capped_exp_backoff(tries):
            backoff_delay = 0
            if tries >=1:
                backoff_delay = min(2**tries, 30) # the sleep won't increase past 30 seconds
            return int(backoff_delay)

        @retryable_job("default", backoff_func=capped_exp_backoff)
        def exponential_backoff_with_limit_task():
            # do some work here or raise an exception

        exponential_backoff_with_limit_task.delay()
    """
    if callable(func_or_queue):
        func = func_or_queue
        queue = "default"
    else:
        func = None
        queue = func_or_queue

    def wrapper(fn):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        set_task_service_name(fn)
        job_team_ns = jobargs.get(TEAM_NS_TAG, None)
        job_service_ns = jobargs.get(SERVICE_NS_TAG, None)
        job_caller = jobargs.get(CALLER_TAG, None)

        def retryable_delay(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            cron_job_name: CronJobName = kwargs.pop(_CRON_JOB_NAME, None)
            if cron_job_name is not None:
                should_enqueue = not should_job_run_in_airflow(cron_job_name)
                if not should_enqueue:
                    logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
                        f"Retryable cron job {cron_job_name} is not going to be scheduled in RQ"
                    )
                    return
                else:
                    logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
                        f"Retryable Cron job {cron_job_name} is going to be scheduled in RQ"
                    )

            default_tags = [f"queue:{str(queue)}", "retryable_job:true"]
            service_ns = kwargs.pop(SERVICE_NS_TAG, job_service_ns)
            team_ns = kwargs.pop(TEAM_NS_TAG, job_team_ns)
            caller = kwargs.pop(CALLER_TAG, job_caller)
            meta = kwargs.pop("meta", {})
            meta[SERVICE_NS_TAG] = service_ns
            meta[TEAM_NS_TAG] = team_ns
            meta[CALLER_TAG] = caller
            meta["default_tags"] = default_tags

            # add retry config
            kwargs.setdefault("retry", set_retry_configs())
            # add on_success/on_failure callback
            # TODO: add on_timeout callback when upgrade RQ to the latest version that supports the interface
            original_on_success_callback = kwargs.pop("on_success", None)
            meta["original_on_success_callback"] = original_on_success_callback
            kwargs.setdefault("on_success", on_success_callback_wrapper)
            original_on_failure_callback = kwargs.pop("on_failure", None)
            meta["original_on_failure_callback"] = original_on_failure_callback
            kwargs.setdefault("on_failure", on_failure_callback_wrapper)
            original_on_stopped_callback = kwargs.pop("on_stopped", None)
            meta["original_on_stopped_callback"] = original_on_stopped_callback
            kwargs.setdefault("on_stopped", on_stopped_callback_wrapper)
            if not meta.get(TRACKING_ID):
                meta[TRACKING_ID] = str(uuid.uuid4())

            kwargs.setdefault("meta", meta)

            # below logic is a quick way to facilitate testing to avoid duplicate logic
            if kwargs.pop("test_helper", False):
                fn.job_cache = {
                    "retry": set_retry_configs(),
                    "on_success": on_success_callback_wrapper,
                    "on_failure": on_failure_callback_wrapper,
                    "on_stopped": on_stopped_callback_wrapper,
                }

            q = _queues[queue]
            queue_host = get_queue_host(q)
            inject_owner_count_metric(
                metric_name="mono.rq_retry.en_queue",
                func=fn,
                tags=default_tags,
                service_ns=service_ns,
                team_ns=team_ns,
                caller=caller,
                queue_host=queue_host,
            )

            try:
                return q.enqueue(fn, *args, **kwargs)
            except Exception as e:
                # in most cases, this indicates a bigger serializer issue for job parameter data
                logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                    # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
                    f"RQ worker has issues to enqueue the retryable job with exception: {e}",
                    exc_info=e,
                    job_name=func.__name__,
                )
                # this is considered as a failure to alert the owner team for job data/logic issues
                inject_owner_count_metric(
                    metric_name="mono.rq_tasks.job_failure",
                    func=fn,
                    tags=default_tags,
                    service_ns=service_ns,
                    team_ns=team_ns,
                    caller=caller,
                    queue_host=queue_host,
                )
                # re-throw so people should be forced to update and fix the issue
                raise e

        def set_retry_configs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
            if retry_limit <= 1:
                return None
            intervals = []
            # this is to mimic the previous implementation
            # we actual only retry for retry_limit - 1 times if the first run fails
            for try_count in range(1, retry_limit):
                intervals.append(backoff_func(try_count))
            return Retry(max=retry_limit - 1, interval=intervals)

        fn.delay = retryable_delay

        return fn

    if func is not None:
        return wrapper(func)

    return wrapper


def schedule_fn(fn, *args: Any, **kwargs: Any) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        logger.info(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
            "Scheduling fn in RQ job",
            fn=fn.__name__,
            args=args,
            kwargs=kwargs,
        )
        fn.delay(*args, **kwargs)

    except RedisError as e:
        stats.increment(
            REDIS_EXCEPTION_SCHEDULING_FN_ERROR_COUNT,
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[
                f"team:{kwargs.get(TEAM_NS_TAG, None)}" f"fn:{fn.__name__}",
            ],
        )
        logger.warning(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
            "Redis exception when scheduling function",
            fn=fn.__name__,
            exception=str(e),
            args=args,
            kwargs=kwargs,
        )
    except Exception as e:
        stats.increment(
            GENERIC_EXCEPTION_SCHEDULING_FN_ERROR_COUNT,
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[
                f"team:{kwargs.get(TEAM_NS_TAG, None)}" f"fn:{fn.__name__}",
            ],
        )
        logger.warning(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "info"
            "Generic exception when scheduling function",
            fn=fn.__name__,
            exception=str(e),
            args=args,
            kwargs=kwargs,
        )


_queues = {
    "default": get_queue(),
    "priority": get_queue("priority"),
    "high_mem": get_queue("high_mem"),
    # this should be used for ad hoc jobs and not for routine or recurring work
    "ad_hoc": get_queue("ad_hoc"),
}
