from __future__ import annotations

import contextlib
import functools
import json
import os
import typing as t
from concurrent import futures

from google import pubsub  # type: ignore[attr-defined]
from google.api_core import exceptions
from maven.observability.contrib import streams

from common import stats
from common.stats import PodNames
from utils import log as utils_log
from utils.gcp import safe_get_project_id
from utils.json import SafeJSONEncoder

log = utils_log.logger(__name__)


def encode_message(message: t.Any) -> bytes:
    return json.dumps(message, cls=SafeJSONEncoder).encode("utf-8")


def publish(
    topic: str,
    *messages: t.Any,
    encoder: t.Callable[[t.Any], bytes] = encode_message,
    pod_name: PodNames = PodNames.UNSET,
    **headers: str,
) -> list[str]:
    """Publishes messages to a Google Pub/Sub topic.

    Args:
        topic: The topic to publish messages to.
        *messages: The messages to publish.
        encoder: The encoder to use.
        pod_name: The name of the engineering pod.
        **headers: Additional headers to send to consumers.
    """
    project_id = safe_get_project_id("development")
    topic_path = pubsub.PublisherClient.topic_path(project_id, topic)
    publisher = get_publisher(topic=topic_path)
    trace_headers, span = streams.producer_span(
        svc=os.getenv("DD_SERVICE", "api"),
        backend="pubsub",
        topic=topic,
        **headers,
    )
    with span:
        if len(messages) > GOOGLE_PUBSUB_MAX_PUBLISH_BATCH_SIZE:
            raise ValueError(
                f"Batch size exceeds Google PubSub max publish size of"
                f" {GOOGLE_PUBSUB_MAX_PUBLISH_BATCH_SIZE}."
            )

        protobufs = [
            pubsub.PubsubMessage(
                data=encoder(e),
                attributes=trace_headers,
            )
            for e in messages
        ]
        response = publisher.publish(
            topic=topic_path,
            messages=protobufs,
        )
        return response.message_ids


# https://cloud.google.com/pubsub/quotas#resource_limits
GOOGLE_PUBSUB_MAX_PUBLISH_BATCH_SIZE: t.Final[int] = 1_000


class PubSubTopics(object):
    PUBSUB_TOPIC_CARE_PLANS_EVENT_OCCURRED = os.getenv(
        "PUBSUB_TOPIC_CARE_PLANS_EVENT_OCCURRED", None
    )


class LogPublisher:
    """Class to act as a publisher in the case that Pub/Sub is not available. If
    there is a problem using Pub/Sub, an instance of LogPublisher is returned by
    get_publisher, and LogPublisher will write the messages to a log file. This
    is most likely to occur in a development environment where a Pub/Sub emulator
    is not running.
    """

    inc = 0

    @classmethod
    def topic_path(cls, *args: t.Any) -> str:
        return "/".join(str(a) for a in args if a)

    def publish(
        self, topic: str, data: t.Any, ordering_key: str = "", **attrs: str
    ) -> futures.Future:
        self.inc += 1
        id = f"<local-{self.inc}>"
        log.info("Publishing message to stdout.", topic=topic, data=data, id=id)
        f = futures.Future()
        f.set_result(id)
        return f


@functools.lru_cache(maxsize=32)
def get_publisher(topic: str | None = None) -> pubsub.PublisherClient:
    """Gets an instance of a PublisherClient or a LogPublisher, depending on what
    is available at the time. This function is largely copied over from
    bq_etl/pubsub_bq/exporter.py with minor modifications.
    """
    log.debug("Initializing the publisher client.")
    try:
        client = pubsub.PublisherClient()
        # If we're running an emulator, try to create the topic
        pubsub_emulator_host = os.getenv("PUBSUB_EMULATOR_HOST")
        if pubsub_emulator_host and topic:
            try:
                client.create_topic({"name": topic})
            except exceptions.AlreadyExists:
                pass
        log.debug("Using GCP PublisherClient.")
        return client
    except Exception as e:
        log.warning(
            "Couldn't connect to GCP. Using local LogPublisher.",
            error=e.__class__.__name__,
        )
        return LogPublisher()


@contextlib.contextmanager
def publisher_error_handler(
    *,
    metric_name: str = "publisher.errors",
    pod_name: PodNames = PodNames.UNSET,
    topic: str,
    tags: list[str] | None = None,
) -> t.Iterator[None]:
    success = "true"
    tags = tags or []
    try:
        yield
    except Exception as e:
        success = "false"
        log.exception(
            f"There was an exception publishing to {topic}: {e}",
            topic=topic,
            metric_name=metric_name,
            tags=tags,
        )
    finally:
        stats.increment(
            metric_name=metric_name,
            pod_name=pod_name,
            tags=[
                f"topic:{topic}",
                f"success:{success}",
            ]
            + tags,
        )
