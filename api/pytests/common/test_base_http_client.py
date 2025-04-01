from unittest import mock

import pytest
from requests import ConnectionError, ConnectTimeout, Response

from common.base_http_client import BaseHttpClient


@pytest.fixture
def http_client():
    return BaseHttpClient(
        base_url="https://mock.mock/",
        service_name="Mock Service",
        headers=None,
        content_type="application/json",
    )


class TestBaseHttpClient:
    def test_success(self, http_client):
        mock_response = Response()
        mock_response.status_code = 200
        mock_response.encoding = "application/json"
        mock_response._content = b"""{"test": "data"}"""
        with mock.patch(
            "common.base_http_client.requests.request", return_value=mock_response
        ) as mock_request:
            response = http_client.make_request("fake_url", method="GET")

        assert mock_request.call_count == 1
        assert mock_request.call_args.kwargs["url"] == "https://mock.mock/fake_url"
        assert response == mock_response
        assert isinstance(response, Response)

    def test_http_error(self, http_client):
        mock_response = Response()
        mock_response.status_code = 422
        with mock.patch(
            "common.base_http_client.requests.request", return_value=mock_response
        ) as mock_request:
            response = http_client.make_request("fake_url", method="GET")

        assert mock_request.call_count == 1
        assert response == mock_response
        assert isinstance(response, Response)

    def test_timeout(self, http_client):
        with mock.patch(
            "common.base_http_client.requests.request",
            side_effect=ConnectTimeout("Timeout Error"),
        ) as mock_request:
            response = http_client.make_request("fake_url", method="GET")

        assert mock_request.call_count == 1
        assert response.status_code == 408
        assert isinstance(response, Response)

    def test_other_error(self, http_client):
        with mock.patch(
            "common.base_http_client.requests.request",
            side_effect=ConnectionError("HTTP Connection Error"),
        ) as mock_request:
            response = http_client.make_request("fake_url", method="GET")

        assert mock_request.call_count == 1
        assert response.status_code == 400
        assert isinstance(response, Response)

    def test_headers(self):
        client = BaseHttpClient(
            service_name="Mock Service",
            headers={"from": "base", "base": "yes"},
            content_type="application/json",
        )

        with mock.patch("common.base_http_client.requests.request") as mock_request:
            client.make_request(
                "fake_url", extra_headers={"from": "call", "call": "yes"}, method="GET"
            )

            assert mock_request.call_args.kwargs["headers"] == {
                "Content-Type": "application/json",
                "from": "call",  # call wins
                "base": "yes",
                "call": "yes",
            }

    def test_retry(self):
        class RetriableClient(BaseHttpClient):
            def _should_retry_on_error(self, error: Exception) -> bool:
                return True

        client = RetriableClient(
            service_name="Mock Service",
            content_type="application/json",
            base_url="http://test.test/",
        )

        mock_response = Response()
        mock_response.status_code = 404
        with mock.patch(
            "common.base_http_client.requests.request", return_value=mock_response
        ) as mock_request:
            client.make_request("fake_url", retry_on_error=True)

        assert mock_request.call_count == 2
        assert mock_request.call_args_list == [
            mock.call(
                method="GET",
                url="http://test.test/fake_url",
                data=None,
                params=None,
                headers={"Content-Type": "application/json"},
                timeout=None,
            ),
            mock.call(
                method="GET",
                url="http://test.test/fake_url",
                data=None,
                params=None,
                headers={"Content-Type": "application/json"},
                timeout=None,
            ),
        ]
