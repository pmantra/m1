from __future__ import annotations

from typing import List

from common import stats
from utils.log import logger
from utils.service_owner_mapper import (
    CALLER_TAG,
    SERVICE_NS_TAG,
    TEAM_NS_TAG,
    service_ns_team_mapper,
)

logger = logger(__name__)

service_ns_list = list(service_ns_team_mapper.keys())
team_ns_set = set(list(service_ns_team_mapper.values()) + ["data"])


def is_service_ns_valid(service_ns: str) -> bool:
    return service_ns is None or service_ns in service_ns_list


def is_team_ns_valid(team_ns: str) -> bool:
    return team_ns is None or team_ns in team_ns_set


def get_pod_name(team_ns: str) -> str:
    if team_ns == "payments":
        return stats.PodNames.PAYMENTS_POD
    if team_ns == "content_and_community":
        return stats.PodNames.COCOPOD

    if team_ns:
        try:
            pod = stats.PodNames(team_ns)
            if pod:
                return pod.value
        except ValueError:
            return stats.PodNames.CORE_SERVICES

    return stats.PodNames.CORE_SERVICES


def inject_owner_count_metric(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    metric_name: str,
    *,
    func=None,
    tags: List[str] = None,  # type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
    service_ns=None,
    team_ns=None,
    caller=None,
    job_func_name=None,
    sample_rate: float = 1,
    queue_host: str | None = None,
) -> bool:
    try:
        tags = [] if tags is None else [*tags]
        task_name = func.__name__ if func else job_func_name
        # NOTE: in the end, both service_ns and team_ns are required by enforcing the sanity check logic
        tags.append(f"{SERVICE_NS_TAG}:{service_ns}")
        tags.append(f"{TEAM_NS_TAG}:{team_ns}")
        tags.append(f"{CALLER_TAG}:{caller}")
        tags.append(f"task_name:{task_name}")
        if queue_host:
            tags.append(f"queue_host:{queue_host}")

        stats.increment(
            metric_name=metric_name,
            pod_name=get_pod_name(team_ns),  # type: ignore[arg-type] # Argument "pod_name" to "increment" has incompatible type "str"; expected "PodNames"
            tags=tags,
            sample_rate=sample_rate,
        )

        return True
    except Exception as e:
        logger.error(  # type: ignore[attr-defined] # "Callable[[str, KwArg(Any)], Any]" has no attribute "error"
            f"[rq-job] exception when adding metrics info before calling delay logic: {e}"
        )

    return False
