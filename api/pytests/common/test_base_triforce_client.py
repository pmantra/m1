from unittest import mock

import pytest

from common.base_triforce_client import BaseTriforceClient


@pytest.fixture
def external_client():
    return BaseTriforceClient(
        base_url="https://mock.mock/",
        service_name="Mock Service",
        headers=None,
        content_type="application/json",
    )


class TestBaseTriforceClient:
    def test_headers(self):
        client = BaseTriforceClient(
            base_url="https://mock.mock/",
            service_name="Mock Service",
            headers={
                "hhh": "http",
                "Cookie": "oatmeal-raisin",
                "Authorization": "some",
            },
            content_type="application/json",
        )

        with mock.patch.object(
            BaseTriforceClient,
            "_fetch_headers_from_request",
            return_value={"rrr": "request", "Cookie": "sugar", "Authorization": "none"},
        ), mock.patch("common.base_http_client.requests.request") as mock_request:
            client.make_service_request(
                url="whos/there",
                extra_headers={"sss": "service", "Cookie": "chocolate-chip"},
            )

            assert (
                mock_request.call_args.kwargs["url"] == "https://mock.mock/whos/there"
            )
            assert mock_request.call_args.kwargs["headers"] == {
                "Content-Type": "application/json",
                "Authorization": "none",  # auth request headers override constructor
                "Cookie": "chocolate-chip",  # auth call headers override request and constructor
                "hhh": "http",  # non-auth headers passed to constructor always present
                # non-auth headers from call and request not present
            }
