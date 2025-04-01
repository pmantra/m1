import fnmatch
import os
import re
import subprocess
from types import SimpleNamespace
from typing import NamedTuple
from unittest import mock

import pytest
from flask import current_app

from models.profiles import Device
from tasks import notifications


# flags that will determine the type of user that is sent a message
class UserProps(NamedTuple):
    is_provider: bool
    is_cx: bool
    is_member: bool


@pytest.fixture()
def messaged_user(factories, request):
    user_props: UserProps = request.param
    if user_props.is_provider:
        user = factories.PractitionerUserFactory.create()
        user.practitioner_profile.phone_number = "(704) 739-6817"
        if not user_props.is_cx:
            user.practitioner_profile.verticals = []
    elif user_props.is_member:
        user = factories.MemberFactory.create()
        user.member_profile.phone_number = "(704) 739-6817"
    return user


@pytest.mark.parametrize(
    "messaged_user",
    [
        # member only
        UserProps(is_provider=False, is_cx=False, is_member=True),
    ],
    indirect=True,
)
def test_notify_member_new_message(factories, messaged_user):
    channel = factories.ChannelFactory.create()
    message = factories.MessageFactory.create(channel_id=channel.id)
    with mock.patch(
        "tasks.notifications._deliver_sms",
        return_value=SimpleNamespace(is_blocked=False),
    ) as mock_deliver_sms:
        notifications.notify_new_message(messaged_user.id, message.id)

    # we are only testing members here
    assert messaged_user.is_member

    assert mock_deliver_sms.called

    user_profile, message_body, _ = mock_deliver_sms.call_args.kwargs.values()
    assert user_profile.phone_number == messaged_user.member_profile.phone_number

    assert message_body is not None
    # message body
    assert (
        re.match(
            r"^You have a new message from a practitioner on Maven(.*)To view this message, visit(.*)",
            message_body,
        )
        is not None
    ), f"Member new message notification body is invalid.\n{message_body}"
    # host url
    assert (
        re.match(
            r"(.*) {url}(.*)".format(url=current_app.config["BASE_URL"]),
            message_body,
        )
        is not None
    ), f"Member new message notification did not contain www app base URL.\n{message_body}"
    # destination path
    assert (
        re.match(r"(.*)/app/messages( |$)", message_body) is not None
    ), f"Member new message notification is pointing to unexpected destination path.\n{message_body}"


@pytest.mark.parametrize(
    "messaged_user",
    [
        # provider only
        UserProps(is_provider=True, is_cx=False, is_member=False),
        # provider and cx
        UserProps(is_provider=True, is_cx=True, is_member=False),
    ],
    indirect=True,
)
def test_notify_practitioner_new_message(factories, messaged_user):
    message = factories.MessageFactory.create()
    with mock.patch(
        "tasks.notifications._deliver_sms",
        return_value=SimpleNamespace(is_blocked=False),
    ) as mock_deliver_sms:
        notifications.notify_new_message(messaged_user.id, message.id)

    # we are only testing practitioners here
    assert messaged_user.is_practitioner

    # ensure we dont notify cx
    if messaged_user.practitioner_profile.is_cx:
        assert not mock_deliver_sms.called
        return

    user_profile, message_body, _ = mock_deliver_sms.call_args.kwargs.values()
    assert user_profile.phone_number == messaged_user.practitioner_profile.phone_number

    assert message_body == "You have a new message on Maven"


@pytest.mark.parametrize(
    "messaged_user",
    [
        # provider
        UserProps(is_provider=True, is_cx=False, is_member=False),
        # member
        UserProps(is_provider=False, is_cx=False, is_member=True),
    ],
    indirect=True,
)
@mock.patch(
    "tasks.notifications.send_practitioner_notification_message",
    return_value=SimpleNamespace(is_blocked=False),
)
@mock.patch(
    "tasks.notifications.send_member_notification_message",
    return_value=SimpleNamespace(is_blocked=False),
)
def test_send_new_message_notification(
    mock_send_member_notification_message,
    mock_send_practitioner_notification_message,
    factories,
    messaged_user,
):
    channel = factories.ChannelFactory.create()
    message = factories.MessageFactory.create(channel_id=channel.id)

    notifications.send_new_message_notification(
        messaged_user, devices=[], message=message
    )

    if messaged_user.is_member:
        assert mock_send_member_notification_message.called
        assert not mock_send_practitioner_notification_message.called

    if messaged_user.is_practitioner:
        assert not mock_send_member_notification_message.called
        assert mock_send_practitioner_notification_message.called


@pytest.mark.parametrize(
    "messaged_user",
    [
        UserProps(is_provider=True, is_cx=False, is_member=False),
        # is cx
        UserProps(is_provider=True, is_cx=True, is_member=False),
    ],
    indirect=True,
)
@mock.patch(
    "tasks.notifications.send_sms",
    return_value=SimpleNamespace(is_blocked=False, is_ok=True),
)
def test_send_practitioner_notification_message(
    mock_send_sms,
    factories,
    messaged_user,
):
    channel = factories.ChannelFactory.create()
    message = factories.MessageFactory.create(channel_id=channel.id)

    notifications.send_practitioner_notification_message(
        messaged_user, devices=[], message=message
    )

    # all users in this test should be practitioners
    assert messaged_user.is_practitioner

    # we dont send notifications to cx's
    if messaged_user.practitioner_profile.is_cx:
        assert not mock_send_sms.called
    else:
        assert mock_send_sms.called


@mock.patch(
    "tasks.notifications.send_sms",
    return_value=SimpleNamespace(is_blocked=False, is_ok=True),
)
def test_send_member_notification_message_with_phone(
    mock_send_sms,
    factories,
):
    user = factories.MemberFactory.create()
    user.member_profile.phone_number = "(704) 739-6817"

    channel = factories.ChannelFactory.create()
    message = factories.MessageFactory.create(channel_id=channel.id)

    notifications.send_member_notification_message(user, devices=[], message=message)
    assert mock_send_sms.called


@mock.patch(
    "tasks.notifications._push_notify_new_message",
    return_value=SimpleNamespace(is_blocked=False),
)
def test_send_member_notification_message_no_phone_with_devices(
    mock_push_notify_new_message,
    factories,
):
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()
    message = factories.MessageFactory.create(channel_id=channel.id)

    notifications.send_member_notification_message(
        user, devices=[Device()], message=message
    )
    assert mock_push_notify_new_message.called


@mock.patch(
    "utils.braze_events.member_new_wallet_message",
    return_value=SimpleNamespace(is_blocked=False),
)
@mock.patch(
    "utils.braze_events.member_new_message",
    return_value=SimpleNamespace(is_blocked=False),
)
def test_send_member_notification_message_no_phone_no_devices_without_wallet(
    mock_member_new_message,
    mock_member_new_wallet_message,
    factories,
):
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()
    message = factories.MessageFactory.create(channel_id=channel.id)

    notifications.send_member_notification_message(user, devices=[], message=message)

    assert not message.channel.is_wallet
    assert mock_member_new_message.called
    assert not mock_member_new_wallet_message.called


@mock.patch(
    "utils.braze_events.member_new_wallet_message",
    return_value=SimpleNamespace(is_blocked=False),
)
@mock.patch(
    "utils.braze_events.member_new_message",
    return_value=SimpleNamespace(is_blocked=False),
)
def test_send_member_notification_message_no_phone_no_devices_with_wallet(
    mock_member_new_message,
    mock_member_new_wallet_message,
    factories,
):
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()

    resource = factories.ResourceFactory(id=5)
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            id=6,
            organization_id=1,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )

    wallet = factories.ReimbursementWalletFactory.create(
        id=1,
        user_id=user.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
    )
    factories.ReimbursementWalletUsersFactory.create(
        user_id=user.id,
        channel_id=channel.id,
        reimbursement_wallet_id=wallet.id,
    )

    message = factories.MessageFactory.create(channel_id=channel.id)

    notifications.send_member_notification_message(user, devices=[], message=message)

    assert message.channel.is_wallet
    assert mock_member_new_wallet_message.called
    assert not mock_member_new_message.called


@pytest.mark.parametrize(
    "messaged_user",
    [
        # provider only
        UserProps(is_provider=True, is_cx=False, is_member=False),
    ],
    indirect=True,
)
def test_construct_practitioner_notification_message_body(factories, messaged_user):
    body = notifications.construct_practitioner_notification_message_body(
        user=messaged_user
    )
    # all notifications have the same message
    assert body == "You have a new message on Maven"


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.get_locale_from_member_preference")
def test_construct_member_notification_message_body_non_wallet_channel(
    mock_get_locale,
    locale,
    country_accepts_url_in_sms_response,
    release_mono_api_localization_on,
    factories,
):
    # Given
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()
    message = factories.MessageFactory.create(channel_id=channel.id)
    mock_get_locale.return_value = locale
    if country_accepts_url_in_sms_response:
        user.member_profile.phone_number = "+17733220000"  # US
    else:
        user.member_profile.phone_number = "+912228403221"  # India

    link_message = {
        "en": "To view this message, visit https://www.mavenclinic.com/app/messages",
        "es": "cta_message_link",
        "fr": "cta_message_link",
        "fr_CA": "cta_message_link",
    }

    message_body = {
        "en": "You have a new message from a practitioner on Maven.",
        "es": "generic_message_body",
        "fr": "generic_message_body",
        "fr_CA": "generic_message_body",
    }

    # When
    body = notifications.construct_member_notification_message_body(
        user=user, message=message
    )
    # Then
    expected_body = message_body[locale]
    if locale == "en":
        if country_accepts_url_in_sms_response:
            expected_body = f"{expected_body} {link_message[locale]}"
            assert fnmatch.fnmatch(body, expected_body)
        else:
            assert body == expected_body
    else:
        assert body != expected_body


@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.get_locale_from_member_preference")
def test_construct_member_notification_message_body_wallet_channel(
    mock_get_locale, locale, release_mono_api_localization_on, factories
):
    # Given:
    mock_get_locale.return_value = locale
    user = factories.MemberFactory.create()
    channel = factories.ChannelFactory.create()

    resource = factories.ResourceFactory(id=5)
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            id=6,
            organization_id=1,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )

    wallet = factories.ReimbursementWalletFactory.create(
        id=1,
        user_id=user.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
    )
    factories.ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=user.id,
        channel_id=channel.id,
    )

    message = factories.MessageFactory.create(channel_id=channel.id)

    # When:
    body = notifications.construct_member_notification_message_body(
        user=user, message=message
    )
    # Then
    message_body = {
        "en": "You have a message about Maven wallet!",
        "es": "wallet_message_body",
        "fr": "wallet_message_body",
        "fr_CA": "wallet_message_body",
    }
    link_message = {
        "en": "To view this message, visit https://www.mavenclinic.com/app/messages",
        "es": "wallet_message_body",
        "fr": "wallet_message_body",
        "fr_CA": "wallet_message_body",
    }
    if locale == "en":
        assert (
            re.match(
                rf"^{message_body[locale]}(.*){link_message[locale]}(.*)",
                body,
            )
            is not None
        ), f"Member new message notification body is invalid for wallet activity.\n{body}"
    else:
        assert (
            re.match(
                rf"^{message_body[locale]}(.*){link_message[locale]}(.*)",
                body,
            )
            is None
        ), f"Member new message notification body is invalid for wallet activity.\n{body}"


def test_notification_cron_jobs():
    """
    Simulates the execution of the notification cron job script and verifies it runs without errors.
    This test ensures that the notification cron jobs called execute successfully without raising any exceptions (e.g. ImportError)
    """

    # Given
    current_dir = os.path.dirname(__file__)
    script_path = os.path.abspath(
        os.path.join(current_dir, "resources/notification_cron_jobs.py")
    )

    try:
        # When
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            check=True,
        )

        # Then
        # If the cron jobs run successfully, we will get a zero error code
        assert result.returncode == 0
    except subprocess.CalledProcessError as e:
        # catch and print the ImportError due to undetected circular imports
        if "ImportError" in e.stderr:
            pytest.fail(f"ImportError occurred: {e.stderr}")
        else:
            pytest.fail(f"Unexpected error occurred: {e.stderr}")
