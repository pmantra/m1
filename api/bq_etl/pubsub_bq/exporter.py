from __future__ import annotations

import functools
import json
import os
from typing import Any

from ddtrace import tracer
from google import (  # type: ignore[attr-defined] # Module "google" has no attribute "pubsub"
    pubsub,
)
from google.api_core import exceptions

from utils.gcp import safe_get_project_id
from utils.json import SafeJSONEncoder
from utils.log import logger

log = logger(__name__)


class LogPublisher:
    inc = 0

    @classmethod
    def topic_path(cls, *args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return "/".join(str(a) for a in args if a)

    def publish(self, topic, data, ordering_key="", **attrs) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self.inc += 1
        return f"<local-{topic}-{self.inc}>"


@functools.lru_cache(maxsize=1)
def get_publisher(topic: str = None) -> pubsub.PublisherClient:  # type: ignore[assignment] # Incompatible default for argument "topic" (default has type "None", argument has type "str")
    project_id = safe_get_project_id()
    if not (project_id and topic):
        return LogPublisher()

    log.debug("Initializing the publisher client.")

    try:
        client = pubsub.PublisherClient()
        # If we're running an emulator, try to create the topic
        pubsub_emulator_host = os.getenv("PUBSUB_EMULATOR_HOST")
        if pubsub_emulator_host and topic:
            try:
                client.create_topic(topic)
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


@tracer.wrap()
def export_rows_to_table(
    table: str = None, rows: list[dict[str, Any]] = None  # type: ignore[assignment] # Incompatible default for argument "table" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "rows" (default has type "None", argument has type "List[Dict[str, Any]]")
) -> str | None:
    if rows is None or len(rows) < 1:
        return None
    log.info("Exporting table", table=table, row_count=len(rows))
    topic = os.getenv("DATA_EXPORT_TOPIC")
    publisher = get_publisher(topic=topic)
    project_id = safe_get_project_id()
    topic_path = publisher.topic_path(project=project_id, topic=topic)
    message_body = {"table": table, "rows": rows}
    message = pubsub.PubsubMessage(
        data=json.dumps(message_body, cls=SafeJSONEncoder).encode("utf-8")
    )
    response: pubsub.PublishResponse = publisher.publish(
        topic=topic_path, messages=[message]
    )
    return response.message_ids[0]
