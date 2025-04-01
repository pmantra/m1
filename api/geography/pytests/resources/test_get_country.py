from maven.feature_flags import test_data


def test_get(default_user, client, api_helpers):
    """
    When:
        - A user requests a list of all current countries
    Then:
        - Return an array of countries and their data
    Test:
        - That a 200 response is sent
        - That a country we are expecting is in the data and has an expected name
    """
    res = client.get(
        "/api/v1/_/geography", headers=api_helpers.standard_headers(default_user)
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    united_states = list(filter(lambda c: c["alpha_2"] == "US", data))
    assert len(united_states) == 1
    assert united_states[0]["name"] == "United States"


def test_gets_translated_countries_with_locale(default_user, client, api_helpers):
    with test_data() as td:
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        td.update(td.flag("release-pycountry-localization").variation_for_all(True))

        res = client.get(
            "/api/v1/_/geography",
            headers=api_helpers.with_locale_header(
                api_helpers.standard_headers(default_user), locale="es"
            ),
        )

    assert res.status_code == 200
    data = api_helpers.load_json(res)
    united_states = list(filter(lambda c: c["alpha_2"] == "US", data))
    assert len(united_states) == 1
    assert united_states[0]["name"] == "Estados Unidos"


def test_gets_english_translations_when_flag_disabled(
    default_user, client, api_helpers
):
    with test_data() as td:
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        td.update(td.flag("release-pycountry-localization").variation_for_all(False))

        res = client.get(
            "/api/v1/_/geography",
            headers=api_helpers.with_locale_header(
                api_helpers.standard_headers(default_user), locale="es"
            ),
        )

    assert res.status_code == 200
    data = api_helpers.load_json(res)
    united_states = list(filter(lambda c: c["alpha_2"] == "US", data))
    assert len(united_states) == 1
    assert united_states[0]["name"] == "United States"
