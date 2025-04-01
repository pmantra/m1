from common.stats import PodNames
from tasks.owner_utils import (
    get_pod_name,
    inject_owner_count_metric,
    is_service_ns_valid,
    is_team_ns_valid,
)


def test_is_service_ns_valid():
    # invalid case
    service_ns = "invalid"
    assert is_service_ns_valid(service_ns=service_ns) is False

    # when the info is None
    service_ns = None
    assert is_service_ns_valid(service_ns=service_ns) is True

    # when the info is valid
    service_ns = "misc"
    assert is_service_ns_valid(service_ns=service_ns) is True


def test_is_team_ns_valid():
    # invalid case
    team_ns = "invalid"
    assert is_team_ns_valid(team_ns=team_ns) is False

    # when the info is None
    team_ns = None
    assert is_team_ns_valid(team_ns=team_ns) is True

    # when the info is valid
    team_ns = "virtual_care"
    assert is_team_ns_valid(team_ns=team_ns) is True


def test_get_pod_name():
    assert get_pod_name(team_ns=None) == PodNames.CORE_SERVICES
    assert get_pod_name(team_ns="invalid") == PodNames.CORE_SERVICES
    assert get_pod_name(team_ns="payments") == PodNames.PAYMENTS_POD
    assert get_pod_name(team_ns="payments_platform") == PodNames.PAYMENTS_PLATFORM
    assert get_pod_name(team_ns="benefits_experience") == PodNames.BENEFITS_EXP
    assert get_pod_name(team_ns="content_and_community") == PodNames.COCOPOD
    assert get_pod_name(team_ns="enrollments") == PodNames.ENROLLMENTS


def test_inject_owner_count_metric():
    assert inject_owner_count_metric(metric_name="dummy") is True
    assert inject_owner_count_metric(metric_name="dummy", team_ns=None) is True

    assert (
        inject_owner_count_metric(
            metric_name="dummy",
            func=inject_owner_count_metric,
            team_ns="core_services",
            service_ns="misc",
        )
        is True
    )
    assert (
        inject_owner_count_metric(metric_name="dummy", func=inject_owner_count_metric)
        is True
    )
    assert (
        inject_owner_count_metric(
            metric_name="dummy",
            team_ns="core_services",
            service_ns="misc",
            job_func_name="test",
        )
        is True
    )
