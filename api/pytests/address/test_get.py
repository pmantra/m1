def test_get_with_no_addresses(default_user, client, api_helpers):
    res = client.get(
        f"/api/v1/users/{default_user.id}/address",
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)

    assert len(json) == 0


def test_get_with_addresses(default_user, client, api_helpers, factories):
    factories.AddressFactory.create(user=default_user)
    res = client.get(
        f"/api/v1/users/{default_user.id}/address",
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)

    assert len(json) == 1
