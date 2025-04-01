from pytests.factories import EnterpriseUserFactory


def test_get(client, api_helpers):
    """Tests that get cancellation policies succeeds"""
    member = EnterpriseUserFactory.create()

    res = client.get(
        "/api/v1/cancellation_policies",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
