def test_get_categories(client, factories, api_helpers):
    user = factories.EnterpriseUserFactory()
    category = factories.ForumsCategoryFactory(
        name="pregnancy", display_name="Pregnancy"
    )

    res = client.get(
        "/api/v1/categories",
        headers=api_helpers.json_headers(user=user),
    )

    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert data["pagination"]["total"] == 1
    assert data["data"][0]["display_name"] == category.display_name
    assert data["data"][0]["name"] == category.name
