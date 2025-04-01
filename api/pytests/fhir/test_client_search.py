from unittest.mock import ANY, call, patch

from utils.fhir_requests import FHIRClient


@patch("utils.fhir_requests.FHIRClient.get_session")
def test_simple_param_construction(get_session, fake_base_url):
    client = FHIRClient()

    with patch.object(client, "handle_response"):
        client.search(a=1, b=2)

    mock_post = get_session.return_value.__enter__.return_value.post
    mock_post.assert_has_calls(
        [
            call(
                f"{fake_base_url}/_search?a=1&b=2",
                headers=ANY,
                data=None,
            )
        ]
    )
