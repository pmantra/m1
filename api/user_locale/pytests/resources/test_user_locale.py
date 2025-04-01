from unittest.mock import patch


def test_get_locale_none(client, api_helpers, default_user):
    user_id = default_user.id
    res = client.get(
        f"/api/v1/users/{user_id}/locale",
        headers=api_helpers.standard_headers(default_user),
    )

    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["locale"] == None


def test_get_locale_en(client, api_helpers, default_user):
    user_id = default_user.id
    with patch(
        "maven.feature_flags.str_variation",
        return_value="en",
    ):
        res = client.get(
            f"/api/v1/users/{user_id}/locale",
            headers=api_helpers.standard_headers(default_user),
        )

    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["locale"] == "en"


def test_get_locale_en_us(client, api_helpers, default_user):
    user_id = default_user.id
    with patch(
        "maven.feature_flags.str_variation",
        return_value="en-US",
    ):
        res = client.get(
            f"/api/v1/users/{user_id}/locale",
            headers=api_helpers.standard_headers(default_user),
        )

    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["locale"] == "en-US"


def test_get_locale_fr(client, api_helpers, default_user):
    user_id = default_user.id
    with patch(
        "maven.feature_flags.str_variation",
        return_value="fr",
    ):
        res = client.get(
            f"/api/v1/users/{user_id}/locale",
            headers=api_helpers.standard_headers(default_user),
        )

    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["locale"] == "fr"


def test_update_locale_supported_locale(client, api_helpers, default_user):
    user_id = default_user.id
    with patch(
        "maven.feature_flags.str_variation",
        return_value="en-US",
    ):
        res = client.put(
            f"/api/v1/users/{user_id}/locale",
            headers=api_helpers.standard_headers(default_user),
            json={"locale": "en-US"},
        )

    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert json["locale"] == "en-US"


def test_update_locale_not_supported_locale(client, api_helpers, default_user):
    user_id = default_user.id
    with patch(
        "maven.feature_flags.str_variation",
        return_value="ja-JP",
    ):
        res = client.put(
            f"/api/v1/users/{user_id}/locale",
            headers=api_helpers.standard_headers(default_user),
            json={"locale": "ja-JP"},
        )

    assert res.status_code == 400
