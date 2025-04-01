from __future__ import annotations

from typing import Optional, Tuple

import flask
from gunicorn.http import message

from utils.log import logger
from utils.service_owner_mapper import get_endpoint_owner_info, workflow_metadata_list

log = logger(__name__)


def get_request_stats(
    request: flask.Request, endpoint_prefix: str = "/api/"
) -> dict[str, str | None]:
    request_id = request.headers.get("X-Request-ID") or request.headers.get(
        "X-Request-Id"
    )
    # set up session ID
    session_id = None
    for header in request.headers.keys():
        # case-insensitive match due to the variations of the header
        if "session" in header.casefold():
            log.info(f"SESSION ID HERE: {request.headers.get(header)}")
            session_id = request.headers.get(header)
            break

    stats = {
        "http.method": request.method,
        "http.x-request-id": request_id,
        "http.x-maven-internal": request.headers.get("x-maven-internal"),
        "http.sentry-trace": request.headers.get("Sentry-Trace"),
        "http.x-real-ip": request.headers.get("X-Real-IP"),
        "http.url": request.base_url,
        "http.device-type": request.headers.get("Device-Model"),
        "http.user-agent": request.headers.get("User-Agent"),
    }
    if request.url_rule:
        view_name = request.url_rule.endpoint.replace(".", "_")
        stats["request.view_name"] = view_name

    service_ns, team_ns, priority, workflows = get_request_owner_info(
        request, endpoint_prefix
    )
    stats["request.service_ns"] = service_ns
    stats["request.team_ns"] = team_ns
    stats["priority"] = priority

    workflow_dict = {workflow: "none" for workflow in workflow_metadata_list}

    for workflow in workflows:
        if workflow in workflow_dict:
            workflow_dict[workflow] = "yes"
    for key, val in workflow_dict.items():
        stats[key] = val

    stats["session_id"] = session_id

    return stats


def get_request_owner_info(
    request: flask.Request | message.Request, endpoint_prefix: str = "/api/"
) -> Tuple[Optional[str], Optional[str], Optional[str], list]:
    # for endpoint owner tagging
    service_ns = team_ns = priority = None
    workflows = []
    try:
        import re

        endpoint = str(request.path)
        match = re.search(endpoint_prefix, endpoint)
        if match:
            sanitized_endpoint = endpoint[match.start() :].strip()
            service_ns, team_ns, priority, workflows = get_endpoint_owner_info(
                sanitized_endpoint, endpoint_prefix
            )
    except Exception as e:
        log.error(f"exception when retrieving the service owner info: {e}")

    return service_ns, team_ns, priority, workflows
