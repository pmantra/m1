from models.profiles import Address


def test_successful_post(default_user, client, api_helpers):
    prev_address_count = Address.query.filter_by(user_id=default_user.id).count()

    res = client.post(
        f"/api/v1/users/{default_user.id}/address",
        headers=api_helpers.standard_headers(default_user),
        json={
            "address_1": "123 Fake Street",
            "city": "Chicago",
            "state": "IL",
            "country": "US",
            "zip_code": "60618",
        },
    )

    second_address_count = Address.query.filter_by(user_id=default_user.id).count()

    assert res.status_code == 201
    assert second_address_count == prev_address_count + 1


def test_post_fails_with_missing_data(default_user, client, api_helpers):
    """
    Missing the address_1 field
    """
    res = client.post(
        f"/api/v1/users/{default_user.id}/address",
        headers=api_helpers.standard_headers(default_user),
        json={"city": "Chicago", "state": "IL", "country": "US", "zip_code": "60618"},
    )

    json_res = api_helpers.load_json(res)

    assert res.status_code == 400
    assert len(json_res["errors"]) == 1
    assert json_res["errors"][0] == {
        "status": 400,
        "title": "Bad Request",
        "detail": "Missing data for required field.",
        "field": "address_1",
    }


def test_post_fails_with_bad_country_code(default_user, client, api_helpers):
    """
    Using an incorrect country code
    """

    res = client.post(
        f"/api/v1/users/{default_user.id}/address",
        headers=api_helpers.standard_headers(default_user),
        json={
            "address_1": "123 Fake Street",
            "city": "Chicago",
            "state": "IL",
            "country": "USA",
            "zip_code": "60618",
        },
    )

    json = api_helpers.load_json(res)

    assert res.status_code == 400
    assert len(json["errors"]) == 1
    assert json["errors"][0] == {
        "status": 400,
        "title": "Bad Request",
        "detail": "USA is not a valid country code!",
        "field": "_schema",
    }


def test_post_fails_with_US_and_bad_state_code(default_user, client, api_helpers):
    """
    it's Indiana
    """

    res = client.post(
        f"/api/v1/users/{default_user.id}/address",
        headers=api_helpers.standard_headers(default_user),
        json={
            "address_1": "123 Fake Street",
            "city": "Chicago",
            "state": "IND",
            "country": "US",
            "zip_code": "60618",
        },
    )

    json_res = api_helpers.load_json(res)

    assert res.status_code == 400
    assert len(json_res["errors"]) == 1
    assert json_res["errors"][0] == {
        "status": 400,
        "title": "Bad Request",
        "detail": "IND is not a valid US state!",
        "field": "_schema",
    }
