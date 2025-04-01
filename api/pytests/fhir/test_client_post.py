from unittest.mock import ANY, call, patch

from utils.fhir_requests import FHIRClient


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_client_post_calls_session_post(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        client.post("foo", data={"a": 1, "b": 2})

    mock_post = get_session.return_value.__enter__.return_value.post
    mock_post.assert_has_calls(
        [call(f"{fake_base_url}/foo", headers=ANY, data='{"a": 1, "b": 2}')]
    )
