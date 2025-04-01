import json

from maven.feature_flags import test_data


def test_get_with_valid_country_code_that_has_subs(default_user, client, api_helpers):
    """
    When:
        - A valid country code is used to GET a country with subdivisions
    Then:
        - Return an array of subdivisions for that country
    Test:
        - That a 200 response is sent
        - That a subdivision we are expecting to see is in the results
    """
    res = client.get(
        "/api/v1/_/geography/US", headers=api_helpers.standard_headers(default_user)
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert "NY" in [s["abbreviation"] for s in data]


def test_get_with_valid_country_code_that_has_no_subs(
    default_user, client, api_helpers
):
    """
    When:
        - A valid country code is used to GET a country with no subdivisions
    Then:
        - Return an empty array
    Test:
        - That a 200 response is sent
        - An empty array is returned
    """
    res = client.get(
        "/api/v1/_/geography/AW", headers=api_helpers.standard_headers(default_user)
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert data == []


def test_get_with_invalid_country_code(default_user, client, api_helpers):
    """
    When:
        - An invalid country code is used to GET subdivisions
    Then:
        - A 400 response and error message is returned
    Test:
        - That a 400 response is sent
        - That the incorrect country code is included in the error message
    """
    res = client.get(
        "/api/v1/_/geography/FF", headers=api_helpers.standard_headers(default_user)
    )
    assert res.status_code == 400
    assert res.json["message"] == "FF is not a valid country code"


def test_get_from_cache(default_user, client, api_helpers, mock_redis_client):
    """
    When:
        - A subdivisions are stored in the cache
    Then:
        - Return an array of subdivisions from the cache
    Test:
        - That a 200 response is sent
        - That a subdivision we are expecting to see is in the results
    """
    cached_value = [
        {
            "subdivision_code": "foo",
            "abbreviation": "FOO",
            "name": "foo",
        }
    ]

    mock_redis_client.get.return_value = json.dumps(cached_value).encode("utf-8")

    res = client.get(
        "/api/v1/_/geography/US", headers=api_helpers.standard_headers(default_user)
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)

    assert data == cached_value


def test_get_localized(default_user, client, api_helpers):
    with test_data() as td:
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        td.update(td.flag("release-pycountry-localization").variation_for_all(True))

        res = client.get(
            "/api/v1/_/geography/NZ",
            headers=api_helpers.with_locale_header(
                api_helpers.standard_headers(default_user), locale="fr"
            ),
        )

    assert res.status_code == 200
    data = api_helpers.load_json(res)

    hawkes_bay = [sd for sd in data if sd["subdivision_code"] == "NZ-HKB"]

    assert len(hawkes_bay) == 1
    assert hawkes_bay[0]["name"] == "Baie de Hawke"
