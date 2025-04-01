from unittest.mock import ANY, call, patch

from utils.fhir_requests import FHIRClient


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_client_patch_calls_session_patch(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        client.patch("foo", data={"a": 1, "b": 2})

    mock_patch = get_session.return_value.__enter__.return_value.patch
    mock_patch.assert_has_calls(
        [call(f"{fake_base_url}/foo", headers=ANY, data='{"a": 1, "b": 2}')]
    )
