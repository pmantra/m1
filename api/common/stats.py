"""
Provides an API for adding datadog's custom metrics into your codebase

Please review our Notion documentation on naming and tagging custom metrics:
https://www.notion.so/mavenclinic/Custom-Metrics-69261e7ea8ed42d98dedf414ae5d2903

Usage:
```
from common import stats

def my function():
    ...business logic...
    stats.increment(...)
```
"""

from enum import Enum
from typing import List

from datadog import statsd

from utils.service_owner_mapper import (
    SERVICE_NS_TAG,
    TEAM_NS_TAG,
    get_owner_tags_from_span,
)

SYS_PREFIX = "mvn"
ENG_POD_TAG = "eng_pod"
ASSOCIATED_METRIC_TAG = "associated_metric_name"


class PodNames(str, Enum):
    MPRACTICE_CORE = "mpractice_core"
    CORE_SERVICES = "core_services"
    ELIGIBILITY = "eligibility"
    PAYMENTS_POD = "payments_pod"
    # content_and_community
    COCOPOD = "cocopod"
    ENROLLMENTS = "enrollments"
    PERSONALIZED_CARE = "personalized_care"
    VIRTUAL_CARE = "virtual_care"
    CARE_DISCOVERY = "care_discovery"
    CARE_KICKOFF = "care_kickoff"
    CARE_MANAGEMENT = "care_management"
    PAYMENTS_PLATFORM = "payments_platform"
    BENEFITS_EXP = "benefits_experience"
    TEST_POD = "__test_pod"
    UNSET = "__unset"

    def __str__(self) -> str:
        return self.value


def increment(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    metric_name: str,
    pod_name: PodNames,
    metric_value: float = 1,
    *,
    sample_rate: float = 1,
    tags: List[str] = None,  # type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
):
    metric_name = f"{SYS_PREFIX}.{metric_name}"
    tags = _add_default_tags(metric_name=metric_name, pod_name=pod_name, tags=tags)

    statsd.increment(metric_name, metric_value, tags=tags, sample_rate=sample_rate)


def gauge(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    metric_name: str,
    pod_name: PodNames,
    metric_value: float,
    *,
    sample_rate: float = 1,
    tags: List[str] = None,  # type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
):
    metric_name = f"{SYS_PREFIX}.{metric_name}"
    tags = _add_default_tags(metric_name=metric_name, pod_name=pod_name, tags=tags)
    statsd.gauge(metric_name, metric_value, tags=tags, sample_rate=sample_rate)


def decrement(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    metric_name: str,
    pod_name: PodNames,
    metric_value: float = 1,
    *,
    sample_rate: float = 1,
    tags: List[str] = None,  # type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
):
    metric_name = f"{SYS_PREFIX}.{metric_name}"
    tags = _add_default_tags(metric_name=metric_name, pod_name=pod_name, tags=tags)
    statsd.decrement(metric_name, metric_value, tags=tags, sample_rate=sample_rate)


def timed(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    metric_name: str,
    pod_name: PodNames,
    *,
    sample_rate: float = 1,
    tags: List[str] = None,  # type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
    use_ms: bool = None,  # type: ignore[assignment] # Incompatible default for argument "use_ms" (default has type "None", argument has type "bool")
):
    metric_name = f"{SYS_PREFIX}.{metric_name}"
    tags = _add_default_tags(metric_name=metric_name, pod_name=pod_name, tags=tags)
    return statsd.timed(metric_name, tags=tags, sample_rate=sample_rate, use_ms=use_ms)


def histogram(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    metric_name: str,
    pod_name: PodNames,
    metric_value: float,
    *,
    sample_rate: float = 1,
    tags: List[str] = None,  # type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
):
    metric_name = f"{SYS_PREFIX}.{metric_name}"
    tags = _add_default_tags(metric_name=metric_name, pod_name=pod_name, tags=tags)
    statsd.histogram(metric_name, metric_value, tags=tags, sample_rate=sample_rate)


def _add_default_tags(metric_name: str, pod_name: PodNames, tags: List[str] = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "tags" (default has type "None", argument has type "List[str]")
    if pod_name not in {*PodNames}:
        raise ValueError(
            f"'{pod_name}' not found in PodNames Enum. Please pass in an enum member or matching member value (ex: PodNames.MY_POD or 'my_pod')"
        )

    tags = [] if tags is None else [*tags]

    if metric_name:
        metric_tag = f"{ASSOCIATED_METRIC_TAG}:{metric_name}"
        tags.append(metric_tag)

    pod_tag = f"{ENG_POD_TAG}:{pod_name}"
    tags.append(pod_tag)

    # add service_ns and team_ns tags as defaults if info exists
    service_ns, team_ns = get_owner_tags_from_span()
    if service_ns:
        tags.append(f"{SERVICE_NS_TAG}:{service_ns}")
        tags.append(f"{TEAM_NS_TAG}:{team_ns}")

    return tags
