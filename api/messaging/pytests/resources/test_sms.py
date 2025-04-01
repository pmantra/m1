import json
from types import SimpleNamespace
from unittest import mock

import pytest
from flask import current_app

from messaging.schemas.sms import SMS_TEMPLATES


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@mock.patch("messaging.resources.sms.send_sms")
def test_post_sms_resource(
    mock_send_sms, country_accepts_url_in_sms_response, client, api_helpers
):

    # Given a phone number from US or india
    if country_accepts_url_in_sms_response:
        phone_number = "+17733220000"  # US
    else:
        phone_number = "+912228403221"  # India

    # When
    res = client.post(
        "/api/v1/unauthenticated/sms",
        data=json.dumps({"phone_number": phone_number, "template": "sms1"}),
        headers=api_helpers.json_headers(None),
    )

    # Then
    assert res.status_code == 200

    if country_accepts_url_in_sms_response:
        mock_send_sms.assert_called_once_with(
            SMS_TEMPLATES["sms1"], "tel:+1-773-322-0000", notification_type="onboarding"
        )
    else:
        mock_send_sms.assert_called_once_with(
            SMS_TEMPLATES["no_url"],
            "tel:+91-22-2840-3221",
            notification_type="onboarding",
        )


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.get_locale_from_member_preference")
@mock.patch("messaging.resources.sms.send_sms")
def test_post_internal_sms_resource(
    mock_send_sms,
    mock_get_locale,
    locale,
    country_accepts_url_in_sms_response,
    release_mono_api_localization_on,
    factories,
    client,
    api_helpers,
):
    # Given
    user = factories.MemberFactory()

    mock_get_locale.return_value = locale
    if country_accepts_url_in_sms_response:
        user.member_profile.phone_number = "+17733220000"  # US
    else:
        user.member_profile.phone_number = "+912228403221"  # India

    # When
    headers = api_helpers.json_headers()
    headers["X-Maven-User-Identities"] = "maven_service"

    res = client.post(
        "/api/v1/-/sms",
        data=json.dumps({"user_id": user.id}),
        headers=headers,
    )

    # Then
    assert res.status_code == 200
    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]
    assert message_arg != "generic_maven_message_body"
    assert (
        f"{current_app.config['BASE_URL']}/app/messages" in message_arg
    ) == country_accepts_url_in_sms_response


@pytest.mark.parametrize("whats_missing", ["phone", "message_content"])
def test_post_internal_sms_resource__missing_phone(
    whats_missing, factories, client, api_helpers
):
    # Given
    user = factories.MemberFactory()
    user.member_profile.phone_number = None

    # When
    headers = api_helpers.json_headers()
    headers["X-Maven-User-Identities"] = "maven_service"

    res = client.post(
        "/api/v1/-/sms",
        data=json.dumps({"user_id": user.id}),
        headers=headers,
    )

    # Then
    assert res.status_code == 400


@mock.patch("messaging.resources.sms.log.exception")
@mock.patch("messaging.resources.sms.send_sms")
def test_post_internal_sms_resource__exception(
    mock_send_sms,
    mock_log,
    factories,
    client,
    api_helpers,
):
    # Given
    user = factories.MemberFactory()

    user.member_profile.phone_number = "+17733220000"  # US

    # When
    headers = api_helpers.json_headers()
    headers["X-Maven-User-Identities"] = "maven_service"

    mock_send_sms.side_effect = Exception
    res = client.post(
        "/api/v1/-/sms",
        data=json.dumps({"user_id": user.id}),
        headers=headers,
    )

    # Then
    assert res.status_code == 500
    args, _ = mock_log.call_args
    assert args[0] == "Exception found when attempting to send SMS"


@mock.patch("messaging.resources.sms.log.warning")
@mock.patch(
    "messaging.resources.sms.send_sms",
    return_value=SimpleNamespace(
        is_blocked=True,
        is_ok=False,
        error_message="test_error_message",
        error_code="test_error_code",
    ),
)
def test_post_internal_sms_resource__blocked_number(
    mock_send_sms,
    mock_log,
    factories,
    client,
    api_helpers,
):
    # Given
    user = factories.MemberFactory()

    user.member_profile.phone_number = "+17733220000"  # US

    # When
    headers = api_helpers.json_headers()
    headers["X-Maven-User-Identities"] = "maven_service"

    res = client.post(
        "/api/v1/-/sms",
        data=json.dumps({"user_id": user.id}),
        headers=headers,
    )

    # Then
    assert res.status_code == 204
    mock_send_sms.assert_called_once()
    args, _ = mock_log.call_args
    assert (
        args[0]
        == "Couldn't send SMS for new Maven message to Member - member profile has a phone number that is sms blocked"
    )


def test_post_sms_resource__validation_error(client, api_helpers):
    # Given a request without a phone number
    data = {"template": "sms1"}

    # When
    res = client.post(
        "/api/v1/unauthenticated/sms",
        data=json.dumps(data),
        headers=api_helpers.json_headers(None),
    )

    # Then
    assert res.status_code == 400
    assert "errors" in res.json
    error = res.json["errors"][0]
    assert "phone_number" in error["field"]
    assert "Missing data" in error["detail"]
