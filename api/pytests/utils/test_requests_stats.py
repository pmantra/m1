from unittest import mock

import pytest

from utils.requests_stats import get_request_stats


@pytest.mark.parametrize(
    argnames="base_url,path,service_ns,team_ns",
    argvalues=[
        (
            "http://api.default.svc.cluster.local/api/v1/appointments",
            "/api/v1/appointments",
            "appointments",
            "care_discovery",
        ),
        (
            "http://api/api/v1/appointments",
            "/api/v1/appointments",
            "appointments",
            "care_discovery",
        ),
        (
            "http://1.1.1.1/api/v1/appointments",
            "/api/v1/appointments",
            "appointments",
            "care_discovery",
        ),
    ],
    ids=["api.default.svc.cluster.local", "api", "ip"],
)
def test_get_request_stats_parses_path(base_url, path, service_ns, team_ns):
    # Given
    mock_request = mock.MagicMock()
    mock_request.headers = mock.MagicMock()
    mock_request.base_url = base_url
    mock_request.path = path

    # When
    stats = get_request_stats(mock_request)

    # Then
    assert stats["request.service_ns"] == service_ns
    assert stats["request.team_ns"] == team_ns
