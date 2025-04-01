from unittest.mock import ANY, call, patch

import pytest

from utils.fhir_requests import FHIRClient


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_simple_param_construction(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        client._request("GET", "foo", params={"a": 1, "b": 2})

    mock_get = get_session.return_value.__enter__.return_value.get
    mock_get.assert_has_calls(
        [call(f"{fake_base_url}/foo?a=1&b=2", headers=ANY, data=None)]
    )


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_or_query_param_construction(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        client._request("GET", "foo", params={"a": [1, 3], "b": [2, 4]})

    mock_get = get_session.return_value.__enter__.return_value.get
    mock_get.assert_has_calls(
        [
            call(
                f"{fake_base_url}/foo?a=1,3&b=2,4",
                headers=ANY,
                data=None,
            )
        ]
    )


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_unsupported_method_raises_error(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        with pytest.raises(ValueError):
            client._request("FAKEMETHOD", "foo")
