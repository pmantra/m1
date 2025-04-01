import json

from maven.feature_flags import test_data


def test_password_strength_score(client, api_helpers):
    data = {"password": "abc12345"}

    response = client.post(
        "/api/v1/_/password_strength_score",
        data=json.dumps(data),
        headers=api_helpers.json_headers(),
    )

    assert response.status_code == 200
    assert len(response.json["feedback"]) == 1
    assert (
        response.json["feedback"][0]
        == "Include 3 of the following 4: uppercase, lowercase, number, and special character !@#$%^&*"
    )


def test_password_strength_score_with_es_locale(client, api_helpers):
    data = {"password": "abc12345"}

    with test_data() as td:
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        response = client.post(
            "/api/v1/_/password_strength_score",
            data=json.dumps(data),
            headers=api_helpers.with_locale_header(
                api_helpers.json_headers(), locale="es"
            ),
        )

    assert response.status_code == 200
    assert len(response.json["feedback"]) == 1
    assert response.json["feedback"][0] != "utils_password_include_3_of_4"


def test_password_length(client, api_helpers):
    data = {"password": "@Ss"}

    response = client.post(
        "/api/v1/_/password_strength_score",
        data=json.dumps(data),
        headers=api_helpers.json_headers(),
    )

    assert response.status_code == 200
    assert len(response.json["feedback"]) == 1
    assert response.json["feedback"][0] == "Password must have at least 8 characters"


def test_password_length_with_es_locale(client, api_helpers):
    data = {"password": "@Ss"}

    with test_data() as td:
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        response = client.post(
            "/api/v1/_/password_strength_score",
            data=json.dumps(data),
            headers=api_helpers.with_locale_header(
                api_helpers.json_headers(), locale="es"
            ),
        )

    assert response.status_code == 200
    assert len(response.json["feedback"]) == 1
    assert response.json["feedback"][0] != "utils_password_minimum_character"
