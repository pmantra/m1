from __future__ import annotations

import datetime
import json
from unittest import mock
from unittest.mock import patch

import flask_babel
import pytest
from marshmallow import ValidationError
from stripe.error import StripeError
from werkzeug.exceptions import BadRequest

from authn.models.user import User
from messaging.logic.message_credit import MessageCreditException
from messaging.models.messaging import Channel, Message, MessageProduct
from messaging.resources.messaging import MessageBillingResource
from models.enterprise import UserAssetState
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import Vertical
from pytests import factories
from storage.connection import db
from utils.constants import MessageCreationFailureReason


# enumerates all key paths within a given object. key paths follow the pattern
# below.
# .data.0.last_message.author.role
# .data.0.last_message.author.encoded_id
# .data.0.last_message.author.profiles.member.has_care_plan
# .data.0.last_message.author.profiles.member.country
# .data.0.last_message.author.profiles.member.tel_number
def key_paths(path, value) -> list[str]:
    if isinstance(value, dict):
        paths = []
        for k in value:
            paths.extend(key_paths(path + "." + k, value[k]))
        return paths
    elif isinstance(value, list):
        paths = []
        if len(value) == 0:
            # ensure empty lists are included in the list of key paths
            paths.extend(key_paths(path + ".", None))
        else:
            for i in range(len(value)):
                paths.extend(key_paths(path + f".{i}", value[i]))
        return paths
    else:
        return [path]


def assert_field_modifications(resp_body: dict):
    resp_key_paths = key_paths("", resp_body)

    # removals
    for path in resp_key_paths:
        # These fields were noted as not used by all client teams
        # https://docs.google.com/spreadsheets/d/1KNVRejXg7xBOgDkvH2SucM81PuAVRtxbs_LybAj9UKk/edit#gid=152098691
        assert not path.endswith("user.profiles.practitioner.subdivision_code")
        assert not path.endswith("user.profiles.practitioner.country_code")
        assert not path.endswith("user.test_group")
        assert not path.endswith("user.feature_flag")
        assert not path.endswith("user.feature_flags")
        assert not path.endswith("user.care_team_with_type")
        assert not path.endswith("last_message.author.profiles.member.subdivision_code")
        assert not path.endswith("last_message.author.profiles.member.dashboard")
        assert not path.endswith("last_message.author.profiles.member.tel_region")
        assert not path.endswith("last_message.author.test_group")

    # changed to static default. validate the key path is present
    required_key_paths = [
        ".user.profiles.practitioner.agreements.subscription",
        ".user.profiles.practitioner.certified_subdivision_codes",
        ".user.care_coordinators",
        ".user.profiles.member.can_book_cx",
    ]
    for required_path in required_key_paths:
        assert any(
            required_path in found_path for found_path in resp_key_paths
        ), f"Expected required key path {required_path} to be present in the response"


@pytest.fixture()
def make_channels():
    def _make_channels(
        num_channels: int = 10,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
        wallet_channel: bool = False,
    ) -> tuple[User, list[Channel]]:
        requesting_user = requesting_user_factory.create()
        now = datetime.datetime.utcnow()

        chans = []

        for i in range(num_channels):
            participant = participant_factory.create()

            factories.MemberTrackFactory.create(user=requesting_user)

            channel = factories.ChannelFactory.create(
                name=f"{requesting_user.first_name}, {participant.first_name}",
                created_at=now + datetime.timedelta(minutes=i),
            )
            channel_user_member = factories.ChannelUsersFactory.create(
                channel_id=channel.id,
                user_id=requesting_user.id,
                channel=channel,
                user=requesting_user,
            )
            channel_user_prac = factories.ChannelUsersFactory.create(
                channel_id=channel.id,
                user_id=participant.id,
                channel=channel,
                user=participant,
            )
            channel.participants = [channel_user_member, channel_user_prac]
            factories.MessageFactory.create(
                channel_id=channel.id,
                user_id=requesting_user.id,
                created_at=now + datetime.timedelta(minutes=i),
            )

            if wallet_channel:
                resource = factories.ResourceFactory(id=channel.id)
                reimbursement_organization_settings = (
                    factories.ReimbursementOrganizationSettingsFactory(
                        id=channel.id,
                        organization_id=channel.id,
                        benefit_faq_resource_id=resource.id,
                        survey_url="fake_url",
                    )
                )
                wallet = factories.ReimbursementWalletFactory.create(
                    id=channel.id,
                    user_id=requesting_user.id,
                    reimbursement_organization_settings_id=reimbursement_organization_settings.id,
                )
                factories.ReimbursementWalletUsersFactory.create(
                    reimbursement_wallet_id=wallet.id,
                    user_id=requesting_user.id,
                    channel_id=channel.id,
                )

            chans.append(channel)
        return (requesting_user, chans)

    return _make_channels


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
def test_get_channels__input_validation_error(
    locale,
    make_channels,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Given a channel
    (member, chans) = make_channels(num_channels=1)

    if locale is None:
        headers = api_helpers.json_headers(user=member)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=member), locale=locale
        )

    # When
    res = client.get(
        "/api/v1/channels?order_direction=invalid_order_direction",
        headers=headers,
    )

    # Then
    assert res.status_code == 400

    assert api_helpers.load_json(res)["message"] != "input_error_getting_channels"


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch("views.schemas.base.MavenSchemaV3.load")
def test_get_channels__serialization_error(
    mock_schema_load,
    locale,
    make_channels,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Mocks setup
    mock_schema_load.side_effect = ValidationError("ValidationError")

    # Given a channel
    (member, chans) = make_channels(num_channels=1)

    if locale is None:
        headers = api_helpers.json_headers(user=member)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=member), locale=locale
        )

    # When
    res = client.get(
        "/api/v1/channels",
        headers=headers,
    )

    # Then
    assert res.status_code == 400

    assert api_helpers.load_json(res)["message"] != "serializing_error_getting_channels"


@pytest.mark.parametrize(
    argnames="is_internal",
    argvalues=[False, True],
)
@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch("messaging.resources.messaging.get_sms_messaging_notifications_enabled")
def test_get_channels(
    mock_notifications_enabled,
    locale,
    is_internal,
    make_channels,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Mocks setup
    mock_notifications_enabled.return_value = True

    # Given a channel
    (member, chans) = make_channels(num_channels=1, wallet_channel=False)

    # When
    chans[0].internal = is_internal
    if locale is None:
        headers = api_helpers.json_headers(user=member)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=member), locale=locale
        )
    res = client.get(
        "/api/v1/channels",
        headers=headers,
    )

    # Then
    assert res.status_code == 200
    resp = json.loads(res.data.decode("utf8"))
    assert resp["message_notifications_consent"]
    assert len(resp["data"]) == 1
    assert resp["data"][0]["id"] == chans[0].id

    # Validate reply_sla
    non_wallet_en_ca_reply_sla = "You'll get a response within 24 hours."
    non_wallet_en_provider_reply_sla = "Most providers respond within 24 hours."

    # First key is boolean if the channel is internal, second is locale
    reply_sla_user_messages = {
        True: {
            None: non_wallet_en_ca_reply_sla,
            "en": non_wallet_en_ca_reply_sla,
            "es": "message_reply_sla_user_message_ca_default",
            "fr": "message_reply_sla_user_message_ca_default",
        },
        False: {
            None: non_wallet_en_provider_reply_sla,
            "en": non_wallet_en_provider_reply_sla,
            "es": "non_wallet_en_provider_reply_sla",
            "fr": "non_wallet_en_provider_reply_sla",
        },
    }
    expected_reply_sla_user_message = reply_sla_user_messages[is_internal][locale]
    if locale is None or locale == "en":
        assert (
            resp["data"][0]["reply_sla_user_message"] == expected_reply_sla_user_message
        )
    else:
        assert (
            resp["data"][0]["reply_sla_user_message"] != expected_reply_sla_user_message
        )


@pytest.mark.parametrize(
    argnames="has_inbound_phone_number",
    argvalues=[False, True],
)
@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch("messaging.schemas.messaging_v3.get_inbound_phone_number")
@patch("messaging.resources.messaging.get_sms_messaging_notifications_enabled")
def test_get_channels__wallet(
    mock_notifications_enabled,
    mock_get_inbound_phone_number_v3,
    locale,
    has_inbound_phone_number,
    make_channels,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Mocks setup
    inbound_phone_number = "tel:555-555-5555"
    mock_get_inbound_phone_number_v3.return_value = (
        inbound_phone_number if has_inbound_phone_number else None
    )
    mock_notifications_enabled.return_value = True

    # Given a channel
    (member, chans) = make_channels(num_channels=1, wallet_channel=True)

    # When
    if locale is None:
        headers = api_helpers.json_headers(user=member)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=member), locale=locale
        )
    res = client.get(
        "/api/v1/channels",
        headers=headers,
    )

    # Then
    assert res.status_code == 200
    resp = json.loads(res.data.decode("utf8"))
    assert resp["message_notifications_consent"]
    assert len(resp["data"]) == 1
    assert resp["data"][0]["id"] == chans[0].id

    # Validate reply_sla
    wallet_no_inbound_number_en_reply_sla = (
        "You'll get a response within 3 business days."
    )
    wallet_with_inbound_number_en_reply_sla = f"You'll get a response within 3 business days. If your matter is urgent, please call us instead at {inbound_phone_number.replace('tel:', '')}."
    wallet_en_reply_sla = (
        wallet_with_inbound_number_en_reply_sla
        if has_inbound_phone_number
        else wallet_no_inbound_number_en_reply_sla
    )

    # First key is if the channel is internal, second is locale
    reply_sla_user_messages = {
        None: wallet_en_reply_sla,
        "en": wallet_en_reply_sla,
        "es": "message_reply_sla_user_message_wallet",
        "fr": "message_reply_sla_user_message_wallet",
    }

    expected_reply_sla_user_message = reply_sla_user_messages[locale]
    if locale is None or locale == "en":
        assert (
            resp["data"][0]["reply_sla_user_message"] == expected_reply_sla_user_message
        )
    else:
        assert (
            resp["data"][0]["reply_sla_user_message"] != expected_reply_sla_user_message
        )


def test_get_channels_for_practitioner(make_channels, client, api_helpers):
    num_channels = 1
    (requesting_user, chans) = make_channels(
        num_channels=num_channels,
        requesting_user_factory=factories.PractitionerUserFactory,
        participant_factory=factories.MemberFactory,
    )

    res = client.get(
        "/api/v1/channels",
        headers=api_helpers.json_headers(user=requesting_user),
    )
    assert res.status_code == 200

    resp = json.loads(res.data.decode("utf8"))
    # print(json.dumps(resp, indent=2))
    assert len(resp["data"]) == num_channels

    for i in range(num_channels):
        # expect in inverse creation order
        assert resp["data"][i]["id"] == chans[num_channels - i - 1].id


def test_get_channels_removed_fields_for_member(
    make_channels,
    client,
    api_helpers,
):
    num_channels = 1
    (member, _) = make_channels(num_channels=num_channels)

    res = client.get(
        "/api/v1/channels",
        data={"user_ids": [member.id]},
        headers=api_helpers.json_headers(user=member),
    )
    assert res.status_code == 200

    resp_body = json.loads(res.data.decode("utf8"))
    assert_field_modifications(resp_body)


def test_get_channels_removed_fields_for_practitioner(
    make_channels,
    client,
    api_helpers,
):
    num_channels = 10
    (requesting_user, _) = make_channels(
        num_channels=num_channels,
        requesting_user_factory=factories.PractitionerUserFactory,
        participant_factory=factories.MemberFactory,
    )

    res = client.get(
        "/api/v1/channels",
        data={"user_ids": [requesting_user.id]},
        headers=api_helpers.json_headers(user=requesting_user),
    )
    assert res.status_code == 200

    resp_body = json.loads(res.data.decode("utf8"))
    assert_field_modifications(resp_body)


@pytest.mark.parametrize(
    argnames="l10_enabled",
    argvalues=[
        False,
        True,
    ],
)
@patch("messaging.resources.messaging.TranslateDBFields.get_translated_vertical")
@patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_get_channels_translated_vertical(
    mock_l10_flag,
    mock_get_translated_verticals,
    l10_enabled,
    make_channels,
    client,
    api_helpers,
):
    # Given
    mock_l10_flag.return_value = l10_enabled
    translated_vertical_name = "translatedverticalname"
    mock_get_translated_verticals.return_value = translated_vertical_name
    (member, channels) = make_channels(
        num_channels=1,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )
    original_vertical = channels[0].practitioner.profile.verticals[0].name
    # When
    db.session.begin_nested()
    res = client.get(
        "/api/v1/channels",
        data={"user_ids": [member.id]},
        headers=api_helpers.json_headers(user=member),
    )
    db.session.rollback()
    # then
    assert res.status_code == 200
    data = res.json["data"]
    assert len(data) == 1
    if l10_enabled:
        assert data[0]["participants"][1]["user"]["profiles"]["practitioner"][
            "verticals"
        ] == [translated_vertical_name]
        vertical = (
            db.session.query(Vertical)
            .filter(Vertical.name == original_vertical)
            .one_or_none()
        )
        assert vertical
    else:
        assert data[0]["participants"][1]["user"]["profiles"]["practitioner"][
            "verticals"
        ] != [translated_vertical_name]


@pytest.mark.skip(
    reason="the add_maven_wallet_participant() method is not using the translation framework yet, also there is only 1 participant"
)
@patch("messaging.resources.messaging.marshmallow_experiment_enabled")
@patch("messaging.resources.messaging.TranslateDBFields.get_translated_vertical")
@patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_get_channels_translated_vertical__wallet(
    mock_l10_flag,
    mock_get_translated_verticals,
    mock_marshammlow_feature_flag,
    wallet_member_channel,
    client,
    api_helpers,
):
    # Given
    mock_marshammlow_feature_flag.return_value = True
    mock_l10_flag.return_value = True
    translated_vertical_name = "translatedverticalname"
    mock_get_translated_verticals.return_value = "translatedverticalname"

    # wallet channel
    member, channel = wallet_member_channel
    practitioner = factories.PractitionerUserFactory()
    original_vertical = practitioner.profile.verticals[0].name
    Channel.get_or_create_channel(practitioner, [member])
    # When
    db.session.begin_nested()
    res = client.get(
        "/api/v1/channels",
        data={"user_ids": [member.id]},
        headers=api_helpers.json_headers(user=member),
    )
    db.session.rollback()
    # Then
    assert res.status_code == 200
    data = res.json["data"]
    assert len(data) == 2
    assert data[1]["participants"][1]["user"]["profiles"]["practitioner"][
        "verticals"
    ] == [translated_vertical_name]
    vertical = (
        db.session.query(Vertical)
        .filter(Vertical.name == original_vertical)
        .one_or_none()
    )
    assert vertical.name != translated_vertical_name


@pytest.mark.parametrize(
    argnames="l10_enabled",
    argvalues=[True, False],
)
@patch("messaging.resources.messaging.TranslateDBFields.get_translated_vertical")
@patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_get_channels_translated_vertical__practitioner(
    mock_l10_flag,
    mock_get_translated_verticals,
    l10_enabled,
    make_channels,
    client,
    api_helpers,
):
    mock_get_translated_verticals.return_value = "translatedverticalname"
    mock_l10_flag.return_value = l10_enabled
    (prac, channels) = make_channels(
        num_channels=1,
        requesting_user_factory=factories.PractitionerUserFactory,
        participant_factory=factories.MemberFactory,
    )
    res = client.get(
        "/api/v1/channels",
        data={"user_ids": [prac.id]},
        headers=api_helpers.json_headers(user=prac),
    )
    assert res.status_code == 200

    data = res.json["data"]
    assert len(data) == 1
    assert data[0]["participants"][0]["user"]["profiles"]["practitioner"][
        "verticals"
    ] != ["translatedverticalname"]


def assert_post_channels(
    user,
    locale,
    request_data,
    expected_status_code,
    expected_message,
    api_helpers,
    client,
):
    # Build headers
    headers = api_helpers.json_headers(user=user)
    if locale:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=user), locale=locale
        )

    # When
    res = client.post(
        "/api/v1/channels",
        data=json.dumps(request_data),
        headers=headers,
    )

    # Then
    assert res.status_code == expected_status_code
    if locale is None or locale == "en":
        assert api_helpers.load_json(res)["message"] == expected_message
    else:
        assert api_helpers.load_json(res)["message"] != expected_message


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
def test_post_channels__cant_open_a_channel_with_only_yourself(
    locale,
    default_user,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Given
    request_data = {}

    # Then
    expected_messages_by_locale = {
        None: "You can't open a channel with only yourself.",
        "en": "You can't open a channel with only yourself.",
        "es": "cant_open_a_channel_with_only_yourself",
        "fr": "cant_open_a_channel_with_only_yourself",
    }
    assert_post_channels(
        user=default_user,
        locale=locale,
        request_data=request_data,
        expected_status_code=400,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
def test_post_channels__you_are_already_included_in_the_channel(
    locale,
    default_user,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Given
    request_data = {"user_ids": [default_user.id]}

    # Then
    expected_messages_by_locale = {
        None: "You are already included in the channel, so you don't need to include yourself in the user_ids.",
        "en": "You are already included in the channel, so you don't need to include yourself in the user_ids.",
        "es": "you_are_already_included_in_the_channel",
        "fr": "you_are_already_included_in_the_channel",
    }
    assert_post_channels(
        user=default_user,
        locale=locale,
        request_data=request_data,
        expected_status_code=400,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
def test_post_channels__we_dont_support_multi_party_messaging(
    locale,
    default_user,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Given
    request_data = {"user_ids": [default_user.id + 1, default_user.id + 2]}

    # Then
    expected_messages_by_locale = {
        None: "We don't support multi-party messaging.",
        "en": "We don't support multi-party messaging.",
        "es": "we_dont_support_multi_party_messaging",
        "fr": "we_dont_support_multi_party_messaging",
    }
    assert_post_channels(
        user=default_user,
        locale=locale,
        request_data=request_data,
        expected_status_code=400,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
def test_post_channels__one_or_more_users_not_found(
    locale,
    default_user,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Given
    request_data = {"user_ids": [default_user.id + 1]}

    # Then
    expected_messages_by_locale = {
        None: "One or more users not found.",
        "en": "One or more users not found.",
        "es": "one_or_more_users_not_found",
        "fr": "one_or_more_users_not_found",
    }
    assert_post_channels(
        user=default_user,
        locale=locale,
        request_data=request_data,
        expected_status_code=400,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
    )


@pytest.mark.parametrize(
    argnames="both_participants_of_type",
    argvalues=["member", "practitioner"],
)
@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
def test_post_channels__channel_can_only_be_opened_between_a_member_and_a_practitioner(
    locale,
    both_participants_of_type,
    client,
    api_helpers,
    factories,
    release_mono_api_localization_on,
):
    # Given
    if both_participants_of_type == "member":
        user1 = factories.MemberFactory()
        user2 = factories.MemberFactory()
    else:
        user1 = factories.PractitionerUserFactory()
        user2 = factories.PractitionerUserFactory()

    request_data = {"user_ids": [user2.id]}

    # Then
    expected_messages_by_locale = {
        None: "Channel can only be opened between a member and a practitioner.",
        "en": "Channel can only be opened between a member and a practitioner.",
        "es": "channel_can_only_be_opened_between_a_member_and_a_practitioner",
        "fr": "channel_can_only_be_opened_between_a_member_and_a_practitioner",
    }
    assert_post_channels(
        user=user1,
        locale=locale,
        request_data=request_data,
        expected_status_code=400,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
    )


@patch("messaging.resources.messaging.notify_new_message")
@patch("messaging.resources.messaging.send_to_zendesk")
@pytest.mark.parametrize(
    argnames=("mock_amount", "expected_status_code"),
    argvalues=[(10, 201), (0, 201)],
    ids=["has_credit", "has_no_credit"],
)
def test_post_message_for_enterprise_member(
    mock_send_to_zendesk,
    mock_notify_new_message,
    mock_amount,
    expected_status_code,
    client,
    api_helpers,
):
    mock_send_to_zendesk.__name__ = "send_to_zendesk"
    mock_notify_new_message.__name__ = "notify_new_message"

    # generate enterprise member details
    member = factories.EnterpriseUserFactory.create(first_name="First")

    # set credit for enterprise member with mock amount
    factories.CreditFactory(user_id=member.id, amount=mock_amount)

    # generate channel details
    channel = factories.ChannelFactory.create(name=member.first_name)
    channel.internal = True
    channel_user_member = factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=member.id, is_initiator=False
    )
    practitioner = factories.PractitionerUserFactory.create()
    channel_user_practitioner = factories.ChannelUsersFactory.create(
        channel_id=channel.id, user_id=practitioner.id, is_initiator=False
    )

    channel.participants = [channel_user_member, channel_user_practitioner]

    message_data = {"body": "test message"}

    res = client.post(
        f"/api/v1/channel/{channel.id}/messages",
        data=api_helpers.json_data(message_data),
        headers=api_helpers.json_headers(user=member),
    )

    assert res.status_code == expected_status_code
    message_id = res.json["id"]
    mock_send_to_zendesk.delay.assert_called_once()
    assert mock_send_to_zendesk.delay.call_args[0][0] == message_id

    mock_notify_new_message.delay.assert_called_once()
    assert mock_notify_new_message.delay.call_args[0][0] == practitioner.id
    assert mock_notify_new_message.delay.call_args[0][1] == message_id


def assert_post_message_to_channel(
    channel,
    user,
    locale,
    expected_failure_reason,
    expected_status_code,
    expected_message,
    api_helpers,
    client,
    mock_increment_message_creation_count_metric,
    message_attachments=None,
    message_body="test message",
):
    message_data = {"body": message_body}
    if message_attachments:
        message_data["attachments"] = message_attachments

    # Build headers
    headers = api_helpers.json_headers(user=user)
    if locale:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=user), locale=locale
        )

    # When
    res = client.post(
        f"/api/v1/channel/{channel.id}/messages",
        data=api_helpers.json_data(message_data),
        headers=headers,
    )

    # Then
    mock_increment_message_creation_count_metric.assert_called_once_with(
        channel.internal,
        channel.is_wallet,
        failure_reason=expected_failure_reason,
    )
    assert res.status_code == expected_status_code
    if locale is None or locale == "en":
        assert api_helpers.load_json(res)["message"] == expected_message
    else:
        assert api_helpers.load_json(res)["message"] != expected_message


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__no_participants_found(
    mock_increment_message_creation_count_metric,
    locale,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    channel = factories.ChannelFactory()
    expected_failure_reason = MessageCreationFailureReason.NO_PARTICIPANT_FOUND
    expected_status_code = 400
    expected_messages_by_locale = {
        None: f"Unable to post message in channel {channel.id}: no participants found",
        "en": f"Unable to post message in channel {channel.id}: no participants found",
        "es": "unable_to_post_message_in_channel_no_participants_found",
        "fr": "unable_to_post_message_in_channel_no_participants_found",
    }

    assert_post_message_to_channel(
        channel=channel,
        user=default_user,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__user_is_not_participant(
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    expected_messages_by_locale = {
        None: "Unable to post message in channel {channel_id}: user is not a participant".format(
            channel_id=channel.id
        ),
        "en": "Unable to post message in channel {channel_id}: user is not a participant".format(
            channel_id=channel.id
        ),
        "es": "unable_to_post_message_in_channel_user_is_not_a_participant",
        "fr": "unable_to_post_message_in_channel_user_is_not_a_participant",
    }
    expected_failure_reason = MessageCreationFailureReason.USER_NOT_A_PARTICIPANT
    expected_status_code = 403

    assert_post_message_to_channel(
        channel=channel,
        user=default_user,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
    )


@pytest.mark.parametrize(
    argnames="reason_for_failure",
    argvalues=["inactive_practitioner", "messaging_disabled_practitioner"],
)
@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__inactive_or_messaging_disabled_practitioner(
    mock_increment_message_creation_count_metric,
    locale,
    reason_for_failure,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    expected_failure_reason = None
    if reason_for_failure == "inactive_practitioner":
        practitioner.practitioner_profile.active = False
        expected_failure_reason = MessageCreationFailureReason.INACTIVE_PRACTITIONER

    elif reason_for_failure == "messaging_disabled_practitioner":
        practitioner.practitioner_profile.messaging_enabled = False
        expected_failure_reason = (
            MessageCreationFailureReason.PRACTITIONER_HAS_MESSAGING_DISABLED
        )

    expected_status_code = 400
    expected_messages_by_locale = {
        None: "Unable to post message in channel {channel_id}: inactive or messaging disabled practitioner".format(
            channel_id=channel.id
        ),
        "en": "Unable to post message in channel {channel_id}: inactive or messaging disabled practitioner".format(
            channel_id=channel.id
        ),
        "es": "unable_to_post_message_in_channel_inactive_or_messaging_disabled_practitioner",
        "fr": "unable_to_post_message_in_channel_inactive_or_messaging_disabled_practitioner",
    }

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__message_is_too_long(
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    message_body = "i" * (Message.MAX_CHARS + 1)

    expected_failure_reason = MessageCreationFailureReason.MESSAGE_TOO_LONG

    expected_status_code = 400
    expected_messages_by_locale = {
        None: "Your message is too long! Please reduce to a maximum of {max_n_chars} characters.".format(
            max_n_chars=Message.MAX_CHARS
        ),
        "en": "Your message is too long! Please reduce to a maximum of {max_n_chars} characters.".format(
            max_n_chars=Message.MAX_CHARS
        ),
        "es": "message_is_too_long",
        "fr": "message_is_too_long",
    }

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
        message_body=message_body,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__could_not_find_asset(
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    invalid_asset_id = "1"
    message_attachments = [invalid_asset_id]

    expected_failure_reason = MessageCreationFailureReason.NO_ASSET_MATCHED

    expected_status_code = 404
    expected_messages_by_locale = {
        None: "Could not find asset matching requested identifier, {asset_id}.".format(
            asset_id=invalid_asset_id
        ),
        "en": "Could not find asset matching requested identifier, {asset_id}.".format(
            asset_id=invalid_asset_id
        ),
        "es": "could_not_find_asset_matching_requested_identifier",
        "fr": "could_not_find_asset_matching_requested_identifier",
    }

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
        message_attachments=message_attachments,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__asset_belonging_to_another_user(
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    asset = factories.UserAssetFactory(user_id=default_user.id)
    message_attachments = [asset.id]
    expected_failure_reason = (
        MessageCreationFailureReason.ASSET_BELONGING_TO_ANOTHER_USER
    )
    expected_status_code = 403
    expected_messages_by_locale = {
        None: "Cannot attach asset belonging to another user",
        "en": "Cannot attach asset belonging to another user",
        "es": "cannot_attach_asset_belonging_to_another_user",
        "fr": "cannot_attach_asset_belonging_to_another_user",
    }

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
        message_attachments=message_attachments,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__asset_not_complete(
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    asset = factories.UserAssetFactory(user_id=member.id)
    asset.state = UserAssetState.UPLOADING
    message_attachments = [asset.id]

    expected_failure_reason = MessageCreationFailureReason.ASSET_NOT_COMPLETE
    expected_status_code = 409
    expected_messages_by_locale = {
        None: "Cannot attach asset to message, asset state is not COMPLETE",
        "en": "Cannot attach asset to message, asset state is not COMPLETE",
        "es": "cannot_attach_asset_to_message_asset_state_is_not_complete",
        "fr": "cannot_attach_asset_to_message_asset_state_is_not_complete",
    }

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
        message_attachments=message_attachments,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__asset_attached_to_multiple_messages(
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    asset = factories.UserAssetFactory(user_id=member.id)
    asset.state = UserAssetState.COMPLETE
    asset.message = factories.MessageFactory()
    message_attachments = [asset.id]

    expected_failure_reason = (
        MessageCreationFailureReason.ATTACH_ASSET_TO_MULTIPLE_MESSAGES
    )
    expected_status_code = 409
    expected_messages_by_locale = {
        None: "Cannot attach asset to multiple messages at once",
        "en": "Cannot attach asset to multiple messages at once",
        "es": "cannot_attach_asset_to_multiple_messages_at_once",
        "fr": "cannot_attach_asset_to_multiple_messages_at_once",
    }
    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
        message_attachments=message_attachments,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
def test_post_message_for_enterprise_member__asset_wrong_content_type(
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    default_user,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member, practitioner, channel = message_member_practitioner_channel
    asset = factories.UserAssetFactory(user_id=member.id)
    asset.state = UserAssetState.COMPLETE
    asset.content_type = "wrong_content_type"
    message_attachments = [asset.id]

    expected_failure_reason = MessageCreationFailureReason.NON_IMAGE_ASSET
    expected_status_code = 409
    expected_messages_by_locale = {
        None: "Only image and PDF file types are supported.",
        "en": "Only image and PDF file types are supported.",
        "es": "only_image_and_pdf_file_types_are_supported",
        "fr": "only_image_and_pdf_file_types_are_supported",
    }

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
        message_attachments=message_attachments,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@pytest.mark.parametrize(
    argnames="user_is_enterprise",
    argvalues=[False, True],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
@patch("messaging.resources.messaging.allocate_message_credits")
def test_post_message_for_enterprise_member__raises_message_credit_exception(
    mock_allocate_message_credits,
    mock_increment_message_creation_count_metric,
    user_is_enterprise,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Given
    mock_allocate_message_credits.side_effect = MessageCreditException(
        user_is_enterprise=user_is_enterprise
    )
    member, practitioner, channel = message_member_practitioner_channel

    if user_is_enterprise:
        expected_messages_by_locale = {
            None: "You do not have enough allowance to message as an enterprise user.",
            "en": "You do not have enough allowance to message as an enterprise user.",
            "es": "exception_allocating_message_credits_enterprise_user",
            "fr": "exception_allocating_message_credits_enterprise_user",
        }
        expected_failure_reason = (
            MessageCreationFailureReason.MESSAGE_CREDITS_ALLOCATION_EXCEPTION_ENTERPRISE
        )
    else:
        expected_messages_by_locale = {
            None: "You do not have enough allowance to message.",
            "en": "You do not have enough allowance to message.",
            "es": "exception_allocating_message_credits_marketplace_user",
            "fr": "exception_allocating_message_credits_marketplace_user",
        }
        expected_failure_reason = (
            MessageCreationFailureReason.MESSAGE_CREDITS_ALLOCATION_EXCEPTION
        )

    expected_status_code = 400

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr"],
)
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
@patch("messaging.resources.messaging.allocate_message_credits")
def test_post_message_for_enterprise_member__raises_generic_exception(
    mock_allocate_message_credits,
    mock_increment_message_creation_count_metric,
    locale,
    message_member_practitioner_channel,
    client,
    api_helpers,
    release_mono_api_localization_on,
):
    # Given
    mock_allocate_message_credits.side_effect = Exception
    member, practitioner, channel = message_member_practitioner_channel

    expected_messages_by_locale = {
        None: "Exception allocating message credits",
        "en": "Exception allocating message credits",
        "es": "general_exception_allocating_message_credits",
        "fr": "general_exception_allocating_message_credits",
    }
    expected_failure_reason = MessageCreationFailureReason.GENERAL_ALLOCATION_EXCEPTION

    expected_status_code = 400

    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=expected_failure_reason,
        expected_status_code=expected_status_code,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
    )


def test_post_message_billing(client, api_helpers, db):
    # Given
    member = factories.DefaultUserFactory()
    product = MessageProduct(number_of_messages=3, price=1)
    db.session.add(product)
    db.session.commit()
    factories.CreditFactory.create(
        amount=10,
        user=member,
    )
    # when:
    res = client.post(
        "/api/v1/message/billing",
        data=api_helpers.json_data({"product_id": product.id}),
        headers=api_helpers.json_headers(member),
    )
    # Then:
    assert res.status_code == 201
    data = api_helpers.load_json(res)
    assert data["available_messages"] == product.number_of_messages


def test_get_message_billing(client, api_helpers):
    # Given:
    member = factories.DefaultUserFactory()
    factories.MessageCreditFactory.create(
        user_id=member.id,
    )
    # When:
    res = client.get(
        "/api/v1/message/billing",
        headers=api_helpers.json_headers(member),
    )
    # Then:
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert data["available_messages"] == 1


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
@mock.patch("messaging.resources.messaging.log.exception")
def test_get_message_billing__exception(
    mock_log_exception, locale, release_mono_api_localization_on, client, api_helpers
):
    # Given:
    member = factories.DefaultUserFactory()
    factories.MessageCreditFactory.create(
        user_id=member.id,
    )
    if locale is None:
        headers = api_helpers.json_headers(user=member)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=member), locale=locale
        )
    # When:
    with patch("storage.connection.db.session.query") as mock_db_query:
        mock_db_query.return_value.filter.return_value.count.side_effect = Exception(
            "this is an exception"
        )
        res = client.get(
            "/api/v1/message/billing",
            headers=headers,
        )
        # Then
        assert res.status_code == 400
        assert res.json["message"] != "available_credits_error"
        mock_log_exception.assert_called()


@pytest.mark.parametrize("locale", ["en", "es", "fr"])
def test__pay_with_card__no_cards(locale, release_mono_api_localization_on):
    # Given:
    member = factories.DefaultUserFactory()
    message_billing = MessageBillingResource()
    # When:
    with flask_babel.force_locale(locale):
        try:
            message_billing._pay_with_card(member, 10)
        # Then
        except BadRequest as e:
            assert e.data["message"] != "no_card_on_file_error"


@pytest.mark.parametrize("locale", ["en", "es", "fr"])
@mock.patch("common.services.stripe.StripeCustomerClient.list_cards")
@mock.patch("common.services.stripe.StripeCustomerClient.create_charge")
def test__pay_with_card__no_charge(
    mock_create_charge,
    mock_list_cards,
    locale,
    release_mono_api_localization_on,
):
    # Given:
    mock_create_charge.return_value = None
    member = factories.DefaultUserFactory()
    mock_list_cards.return_value = [member]
    message_billing = MessageBillingResource()
    # When:
    with flask_babel.force_locale(locale):
        try:
            message_billing._pay_with_card(member, 10)
        # Then
        except BadRequest as e:
            assert e.data["message"] != "cannot_charge_customer_error"


@pytest.mark.parametrize("locale", ["en", "es", "fr"])
@mock.patch("messaging.resources.messaging.log.error")
@mock.patch("common.services.stripe.StripeCustomerClient.list_cards")
@mock.patch("common.services.stripe.StripeCustomerClient.create_charge")
def test__pay_with_card__stripe_error(
    mock_create_charge,
    mock_list_cards,
    mock_log_error,
    locale,
    release_mono_api_localization_on,
):
    # Given
    mock_create_charge.side_effect = StripeError("blah")
    member = factories.DefaultUserFactory()
    mock_list_cards.return_value = [member]
    message_billing = MessageBillingResource()
    # When:
    with flask_babel.force_locale(locale):
        try:
            message_billing._pay_with_card(member, 10)
        # Then
        except BadRequest as e:
            assert e.data["message"] != "cannot_charge_customer_stripe_error"
    mock_log_error.assert_called()


@mock.patch("views.schemas.common.should_enable_can_member_interact")
@pytest.mark.parametrize("is_enterprise", [True, False])
@pytest.mark.parametrize("flag_value", [True, False])
def test__get_channel_status(
    should_enable_can_member_interact, is_enterprise, flag_value, client, api_helpers
):
    # given:
    should_enable_can_member_interact.return_value = flag_value
    if is_enterprise:
        member = factories.EnterpriseUserFactory.create()
    else:
        member = factories.DefaultUserFactory.create()
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="OB-GYN")
        ]
    )
    channel = Channel.get_or_create_channel(practitioner, [member])
    # when
    res = client.get(
        f"/api/v1/channel/{channel.id}/status",
        headers=api_helpers.json_headers(member),
    )

    # then
    assert res.status_code, 200
    res_data = json.loads(res.data)

    assert res_data["participants"][1]["user"]["profiles"]["practitioner"][
        "can_member_interact"
    ]
    assert len(res_data["participants"][0]["user"]["active_tracks"]) == (
        1 if is_enterprise else 0
    )
    assert len(res_data["participants"][1]["user"]["active_tracks"]) == 0


@pytest.mark.parametrize(
    "is_doula_only_track,vertical_name,",
    [(True, "Doula and childbirth educator"), (False, "OB-GYN")],
)
@patch("views.schemas.common.should_enable_can_member_interact")
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test__get_channel_status__doula_only(
    mock_should_enable_doula_only_track,
    mock_should_enable_can_member_interact,
    is_doula_only_track,
    vertical_name,
    client,
    api_helpers,
    create_doula_only_member,
):
    # given:
    mock_should_enable_can_member_interact.return_value = True
    member = create_doula_only_member

    active_member_track = member.active_tracks[0]
    client_track_id = active_member_track.client_track_id

    vertical = factories.VerticalFactory.create(name=vertical_name)

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    factories.VerticalAccessByTrackFactory.create(
        client_track_id=client_track_id,
        vertical_id=vertical.id,
        track_modifiers=TrackModifiers.DOULA_ONLY if is_doula_only_track else None,
    )

    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical]
    )
    channel = Channel.get_or_create_channel(practitioner, [member])
    # when
    res = client.get(
        f"/api/v1/channel/{channel.id}/status",
        headers=api_helpers.json_headers(member),
    )

    # then
    assert res.status_code, 200
    res_data = json.loads(res.data)

    assert (
        res_data["participants"][1]["user"]["profiles"]["practitioner"][
            "can_member_interact"
        ]
        == is_doula_only_track
    )

    assert res_data["participants"][0]["user"]["active_tracks"][0][
        "track_modifiers"
    ] == [TrackModifiers.DOULA_ONLY]


@mock.patch("views.schemas.common.should_enable_can_member_interact")
@pytest.mark.parametrize("flag_value", [True, False])
def test__get_channel_status__wallet_channel(
    should_enable_can_member_interact, flag_value, client, api_helpers
):
    # given: wallet channel
    should_enable_can_member_interact.return_value = flag_value
    member = factories.EnterpriseUserFactory.create()
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="OB-GYN")
        ]
    )
    channel = Channel.get_or_create_channel(practitioner, [member])
    resource = factories.ResourceFactory(id=channel.id)
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            id=channel.id,
            organization_id=channel.id,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )
    wallet = factories.ReimbursementWalletFactory.create(
        id=channel.id,
        user_id=member.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
    )
    factories.ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=member.id,
        channel_id=channel.id,
    )
    # add messages from wallet reimbursement
    factories.MessageFactory.create(channel_id=channel.id)
    # when
    res = client.get(
        f"/api/v1/channel/{channel.id}/status",
        headers=api_helpers.json_headers(member),
    )

    # then
    assert res.status_code, 200
    res_data = json.loads(res.data)

    assert res_data["participants"][2]["user"]["profiles"]["practitioner"][
        "can_member_interact"
    ]


@pytest.mark.parametrize(
    argnames="l10_enabled",
    argvalues=[
        False,
        True,
    ],
)
@patch("messaging.resources.messaging.TranslateDBFields.get_translated_vertical")
@patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_get_channel_status__translated_vertical(
    mock_l10_flag,
    mock_get_translated_verticals,
    l10_enabled,
    make_channels,
    client,
    api_helpers,
):
    mock_l10_flag.return_value = l10_enabled
    mock_get_translated_verticals.return_value = "translatedverticalname"
    (member, channels) = make_channels(
        num_channels=1,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )
    # when
    res = client.get(
        f"/api/v1/channel/{channels[0].id}/status",
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 200
    data = json.loads(res.data)
    if l10_enabled:
        assert data["participants"][1]["user"]["profiles"]["practitioner"][
            "verticals"
        ] == ["translatedverticalname"]
    else:
        assert data["participants"][1]["user"]["profiles"]["practitioner"][
            "verticals"
        ] != ["translatedverticalname"]


@pytest.mark.parametrize(
    argnames="l10_enabled",
    argvalues=[True, False],
)
@patch("messaging.resources.messaging.TranslateDBFields.get_translated_vertical")
@patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_get_channel_status__translated_vertical_practitioner(
    mock_l10_flag,
    mock_get_translated_verticals,
    l10_enabled,
    make_channels,
    client,
    api_helpers,
):
    mock_l10_flag.return_value = l10_enabled
    mock_get_translated_verticals.return_value = "translatedverticalname"
    (prac, channels) = make_channels(
        num_channels=1,
        requesting_user_factory=factories.PractitionerUserFactory,
        participant_factory=factories.MemberFactory,
    )
    # when
    res = client.get(
        f"/api/v1/channel/{channels[0].id}/status",
        headers=api_helpers.json_headers(prac),
    )
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["participants"][0]["user"]["profiles"]["practitioner"]["verticals"] != [
        "translatedverticalname"
    ]


@pytest.mark.parametrize("locale", [None, "en", "es", "fr", "fr_CA"])
@patch(
    "messaging.resources.messaging.ChannelMessagesResource._increment_message_creation_count_metric"
)
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_post_message_for_enterprise_member__doula_only_not_allowed(
    mock_should_enable_doula_only_track,
    mock_increment_message_creation_count_metric,
    locale,
    create_doula_only_member,
    client,
    api_helpers,
    factories,
    release_mono_api_localization_on,
):
    # Given
    member = create_doula_only_member
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="OB-GYN")
        ]
    )
    channel = Channel.get_or_create_channel(practitioner, [member])

    expected_messages_by_locale = {
        None: "Unable to post message, member cannot message this provider.",
        "en": "Unable to post message, member cannot message this provider.",
        "es": "unable_to_post_message_in_channel_member_cannot_message_practitioner",
        "fr": "unable_to_post_message_in_channel_member_cannot_message_practitioner",
        "fr_CA": "unable_to_post_message_in_channel_member_cannot_message_practitioner",
    }
    # when / then
    assert_post_message_to_channel(
        channel=channel,
        user=member,
        locale=locale,
        expected_failure_reason=MessageCreationFailureReason.MEMBER_CANNOT_MESSAGE_PRACTITIONER,
        expected_status_code=400,
        expected_message=expected_messages_by_locale[locale],
        api_helpers=api_helpers,
        client=client,
        mock_increment_message_creation_count_metric=mock_increment_message_creation_count_metric,
    )


@pytest.mark.parametrize(
    "include_empty",
    [
        True,
        False,
    ],
)
@mock.patch("messaging.resources.messaging.filter_channels")
def test_get_channels_filter_no_messages(
    mock_filter_channels,
    make_channels,
    client,
    api_helpers,
    include_empty,
):
    num_channels = 1
    (member, channels) = make_channels(num_channels=num_channels)

    res = client.get(
        f"/api/v1/channels?empty={include_empty}",
        data={"user_ids": [member.id]},
        headers=api_helpers.json_headers(user=member),
    )
    assert res.status_code == 200
    mock_filter_channels.assert_called_once_with(
        channels,
        include_wallet=True,
        include_no_messages=include_empty,
    )


@pytest.mark.parametrize("is_wallet", [True, False])
def test_get_channels_unread_messages(is_wallet, make_channels, client, api_helpers):

    # Given
    (member, chans) = make_channels(
        num_channels=1,
        wallet_channel=is_wallet,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )

    channel = chans[0]
    prac = channel.practitioner

    # When
    # first send a message to the channel as a practitioner that has yet to be read by the member
    message_data = {"body": "test message"}

    client.post(
        f"/api/v1/channel/{channel.id}/messages",
        data=api_helpers.json_data(message_data),
        headers=api_helpers.json_headers(user=prac),
    )

    res = client.get(
        "/api/v1/channels/unread",
        headers=api_helpers.json_headers(user=member),
    )

    # Then
    assert res.status_code == 200
    channel_message_count = res.json["count"]
    assert channel_message_count == 1


@pytest.mark.parametrize("marshmallow_v3_enabled", [True, False])
@pytest.mark.parametrize("wallet_channels", [True, False])
@mock.patch("models.enterprise.signed_cdn_url")
@mock.patch("messaging.resources.messaging.marshmallow_experiment_enabled")
def test_get_channels_message(
    mock_marshmallow_flag,
    mock_cdn_url,
    marshmallow_v3_enabled,
    client,
    api_helpers,
    make_channels,
    wallet_channels,
):
    mock_cdn_url.return_value = "https://mock_url.com"
    mock_marshmallow_flag.return_value = marshmallow_v3_enabled
    # Given - channel with message + attachment
    (member, chans) = make_channels(
        num_channels=1,
        wallet_channel=wallet_channels,
        requesting_user_factory=factories.MemberFactory,
        participant_factory=factories.PractitionerUserFactory,
    )

    channel = chans[0]
    asset = factories.UserAssetFactory(user_id=member.id)
    factories.MessageFactory.create(
        body="test message",
        channel_id=channel.id,
        user_id=member.id,
        created_at=datetime.datetime.utcnow(),
        attachments=[asset],
    )

    # When
    res = client.get(
        f"/api/v1/channel/{channel.id}/messages",
        headers=api_helpers.json_headers(user=member),
    )

    # Then
    assert res.status_code == 200
    content = res.json
    # assert two messages, one initial one w attachment
    assert len(content["data"]) == 2
    message_data = content["data"][0]
    # assert attachment came through
    assert message_data["attachments"] != []
    assert message_data["attachments"][0]["thumbnail"] == "https://mock_url.com"
    assert message_data["body"] == "test message"
    assert message_data["author"]["first_name"] == member.first_name
    assert message_data["meta"][0]["is_read"] is True
    assert message_data["meta"][0]["is_acknowledged"] is False
    assert message_data["meta"][0]["user_id"] == member.id


@patch("messaging.resources.messaging.log.info")
def test_post_message_notifications_consent_resource(
    mock_log_info, client, api_helpers, enterprise_user
):
    # Given
    user = enterprise_user
    # When
    res = client.post(
        "/api/v1/message/notifications_consent",
        headers=api_helpers.json_headers(user=user),
    )

    # Then
    assert res.status_code == 200
    assert mock_log_info.called_once_with(
        "setting sms consent as true", user_id=user.id
    )


def test_get_message_notifications_consent_resource(
    client, api_helpers, enterprise_user
):
    # Given
    user = enterprise_user
    # When
    res = client.get(
        "/api/v1/message/notifications_consent",
        headers=api_helpers.json_headers(user=user),
    )

    # Then
    assert res.status_code == 200
    assert res.json["message_notifications_consent"] is False
