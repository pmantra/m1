from unittest.mock import ANY, call, patch

from utils.fhir_requests import FHIRClient


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_client_delete_calls_session_delete(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        client.delete("foo")

    mock_delete = get_session.return_value.__enter__.return_value.delete
    mock_delete.assert_has_calls([call(f"{fake_base_url}/foo", headers=ANY, data=None)])
