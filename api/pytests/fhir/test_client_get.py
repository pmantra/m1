from unittest.mock import ANY, call, patch

from utils.fhir_requests import FHIRClient


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_client_get_calls_session_get(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        client.get("foo")

    mock_get = get_session.return_value.__enter__.return_value.get
    mock_get.assert_has_calls([call(f"{fake_base_url}/foo", headers=ANY, data=None)])
