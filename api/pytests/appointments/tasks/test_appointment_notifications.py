import datetime
import fnmatch
from collections import namedtuple
from unittest import mock

import pytest
from flask import current_app

from appointments.models import practitioner_appointment
from appointments.tasks.appointment_notifications import (
    BOOKINGS_ENTERPRISE_VIP_ORGANIZATION,
    _notify_bookings_channel,
    cancel_member_appointment_confirmation,
    confirm_booking_sms_notifications_to_practitioner,
    notify_about_new_appointment,
    notify_about_upcoming_noshows,
    notify_bookings_about_new_appointment,
    notify_vip_bookings,
    schedule_member_appointment_confirmation_sms,
    schedule_member_confirm_appointment_sms,
    send_member_cancellation_note,
    send_practitioner_cancellation_note,
    send_slack_cancellation,
    sms_notify_member_about_new_appointment,
    sms_notify_upcoming_appointments_member,
    sms_notify_upcoming_appointments_practitioner,
)
from models.enterprise import Organization
from pytests import freezegun
from storage.connection import db
from utils import braze_events


@pytest.fixture()
# request = (is_enterprise,is_vip,is_ca)
# Only one should be on (limitations with factory params)
def upcoming_appointment(factories, request):
    is_enterprise, is_vip, is_ca = request.param
    now = datetime.datetime.utcnow()
    appointment = factories.AppointmentFactory.create(
        scheduled_start=now + datetime.timedelta(hours=2),
        product__price=10,
        is_enterprise_factory=is_enterprise,
        is_enterprise_with_track_factory=is_vip,
    )

    # is_vip => Set organization.name
    if is_vip:
        appointment.member.organization.name = BOOKINGS_ENTERPRISE_VIP_ORGANIZATION
    if is_ca:
        practitioner = factories.PractitionerUserFactory.create()
        vertical = factories.VerticalFactory.create_cx_vertical()
        practitioner.practitioner_profile.verticals.append(vertical)
        appointment.product.practitioner = practitioner

    return appointment


@pytest.fixture()
@freezegun.freeze_time(datetime.datetime.now() - datetime.timedelta(hours=1))
# request = (is_enterprise,is_vip)
# Only one should be on (limitations with factory params)
def insert_noshow_appointment(factories, request):
    is_enterprise, is_vip = request.param
    now = datetime.datetime.now()

    # Create the appointment
    appointment = factories.AppointmentFactory.create(
        scheduled_start=now,
        product__price=10,
        is_enterprise_factory=is_enterprise,
        is_enterprise_with_track_factory=is_vip,
    )

    # Manually create the PractitionerAppointmentAck, no factory exists :(
    ack = practitioner_appointment.PractitionerAppointmentAck(
        appointment=appointment,
        phone_number="+12125555555",
        ack_by=now,
        warn_by=now,
        is_acked=False,
        is_alerted=False,
    )
    db.session.add(ack)
    db.session.commit()

    # is_vip => Set organization.name (we need the database updated too)
    if is_vip:
        appointment.member.organization.name = BOOKINGS_ENTERPRISE_VIP_ORGANIZATION
        organization = Organization.query.get(appointment.member.organization.id)
        organization.name = appointment.member.organization.name
        db.session.commit()

    return appointment


# Basic VIP notify test
@pytest.mark.parametrize("upcoming_appointment", [(True, True, False)], indirect=True)
def test_notify_vip_bookings_vip(upcoming_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_notify_vip_bookings_channel:
        notify_vip_bookings(
            upcoming_appointment.member, "Test Title", "This is a test message"
        )

    mock_notify_vip_bookings_channel.assert_called_once()
    mock_notify_vip_bookings_channel.assert_called_with(
        "Test Title", "This is a test message"
    )


# Basic non-VIP notify test
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
def test_notify_vip_bookings_not_vip(upcoming_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_notify_vip_bookings_channel:
        notify_vip_bookings(
            upcoming_appointment.member, "Test Title", "This is a test message"
        )

    mock_notify_vip_bookings_channel.assert_not_called()


# Factory standard user notify booking test with details
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
def test__notify_bookings_channel(upcoming_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_bookings_channel"
    ) as mock_notifify_bookings_channel:
        _notify_bookings_channel(upcoming_appointment)

    mock_notifify_bookings_channel.assert_called_once()
    actual_message = mock_notifify_bookings_channel.call_args[0][0]
    assert upcoming_appointment.practitioner.full_name in actual_message
    assert upcoming_appointment.practitioner.email in actual_message
    assert "External" in actual_message
    assert f"?id={upcoming_appointment.id}" in actual_message
    assert upcoming_appointment.starts_in() in actual_message


# Factory VIP notify booking test
@pytest.mark.parametrize("upcoming_appointment", [(False, True, False)], indirect=True)
def test__notify_bookings_channel_vip(upcoming_appointment):
    # Set the correct org name
    upcoming_appointment.member.organization.name = BOOKINGS_ENTERPRISE_VIP_ORGANIZATION

    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_notifify_vip_bookings:
        notify_vip_bookings(
            upcoming_appointment.member,
            "VIP appointment notification",
            "Test Message",
        )

    mock_notifify_vip_bookings.assert_called_once()


# Factory Non-VIP notify booking test
@pytest.mark.parametrize("upcoming_appointment", [(False, True, False)], indirect=True)
def test__notify_bookings_channel_non_vip(upcoming_appointment):
    # Set the wrong org name
    upcoming_appointment.member.organization.name = "LucasArts"

    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_notifify_vip_bookings:
        notify_vip_bookings(
            upcoming_appointment.member,
            "VIP appointment notification",
            "Test Message",
        )

    mock_notifify_vip_bookings.assert_not_called()


# Noshow appointment standard user notify test
@pytest.mark.parametrize("insert_noshow_appointment", [(False, False)], indirect=True)
def test_notify_about_upcoming_noshows(insert_noshow_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_bookings_channel"
    ) as mock_notify_about_upcoming_noshows:
        notify_about_upcoming_noshows()

    mock_notify_about_upcoming_noshows.assert_called()


# Noshow appointment enterprise user notify test
@pytest.mark.parametrize("insert_noshow_appointment", [(True, False)], indirect=True)
def test_notify_about_upcoming_noshows_enterprise(insert_noshow_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_bookings_channel"
    ) as mock_notify_about_upcoming_noshows:
        notify_about_upcoming_noshows()

    mock_notify_about_upcoming_noshows.assert_called()


# Noshow appointment vip user notify test
@pytest.mark.parametrize("insert_noshow_appointment", [(False, True)], indirect=True)
def test_notify_about_upcoming_noshows_vip(insert_noshow_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_notify_about_upcoming_noshows:
        notify_about_upcoming_noshows()

    mock_notify_about_upcoming_noshows.assert_called()


# Cancel appointment standard user notify test
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
def test_send_slack_cancellation(upcoming_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_bookings_channel"
    ) as mock_send_slack_cancellation:
        send_slack_cancellation(upcoming_appointment)

    mock_send_slack_cancellation.assert_called()


# Cancel appointment enterprise user notify test
@pytest.mark.parametrize("upcoming_appointment", [(True, False, False)], indirect=True)
def test_send_slack_cancellation_enterprise(upcoming_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_enterprise_bookings_channel"
    ) as mock_send_slack_cancellation:
        send_slack_cancellation(upcoming_appointment)

    mock_send_slack_cancellation.assert_called()


# Cancel appointment vip user notify test
@pytest.mark.parametrize("upcoming_appointment", [(False, True, False)], indirect=True)
def test_send_slack_cancellation_vip(upcoming_appointment):
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_send_slack_cancellation:
        send_slack_cancellation(upcoming_appointment)

    mock_send_slack_cancellation.assert_called()


# Test notify_about_new_appointment after prod issue with vip
@pytest.mark.parametrize("upcoming_appointment", [(False, True, False)], indirect=True)
def test_notify_about_new_appointment_vip(upcoming_appointment):
    with mock.patch("ddtrace.tracer.trace"), mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings"
    ) as mock_notify_about_new_appointment_vip:
        notify_bookings_about_new_appointment(upcoming_appointment.id)

    mock_notify_about_new_appointment_vip.assert_called_once()


# Test to ensure that Non-CAs get an SMS message sent for new appointments
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
def test_notify_about_new_appointment_no_ca(upcoming_appointment):
    with mock.patch("utils.braze_events.appointment_booked_practitioner"), mock.patch(
        "appointments.tasks.appointment_notifications.notify_bookings_about_new_appointment.delay"
    ) as mock_notify_bookings, mock.patch(
        "appointments.tasks.appointment_notifications.confirm_booking_email_to_practitioner.delay"
    ) as mock_notify_email, mock.patch(
        "appointments.tasks.appointment_notifications.confirm_booking_sms_notifications_to_practitioner.delay"
    ) as mock_notify_push, mock.patch(
        "appointments.tasks.appointment_notifications.confirm_booking_push_notifications_to_practitioner.delay"
    ) as mock_notify_sms:
        notify_about_new_appointment(upcoming_appointment.id)

    # non CA we should have 4 alerts: bookings channel, email, push, sms
    mock_notify_bookings.assert_called_once()
    mock_notify_email.assert_called_once()
    mock_notify_push.assert_called_once()
    mock_notify_sms.assert_called_once()


# Test to ensure that CAs DO NOT get an SMS message sent for new appointments
@pytest.mark.parametrize("upcoming_appointment", [(False, False, True)], indirect=True)
def test_notify_about_new_appointment_ca(upcoming_appointment):
    with mock.patch("utils.braze_events.appointment_booked_practitioner"), mock.patch(
        "appointments.tasks.appointment_notifications.notify_bookings_about_new_appointment.delay"
    ) as mock_notify_bookings, mock.patch(
        "appointments.tasks.appointment_notifications.confirm_booking_email_to_practitioner.delay"
    ) as mock_notify_email, mock.patch(
        "appointments.tasks.appointment_notifications.confirm_booking_sms_notifications_to_practitioner.delay"
    ) as mock_notify_push, mock.patch(
        "appointments.tasks.appointment_notifications.confirm_booking_push_notifications_to_practitioner.delay"
    ) as mock_notify_sms:
        notify_about_new_appointment(upcoming_appointment.id)

    # CA only gets bookings and email, not SMS or push
    mock_notify_bookings.assert_called_once()
    mock_notify_email.assert_called_once()
    mock_notify_push.assert_not_called()
    mock_notify_sms.assert_not_called()


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
@mock.patch("appointments.tasks.appointment_notifications.send_sms")
@mock.patch("appointments.tasks.appointment_notifications.country_accepts_url_in_sms")
def test_confirm_booking_sms_notifications_to_practitioner(
    mock_country_accepts_url_in_sms,
    mock_send_sms,
    upcoming_appointment,
    country_accepts_url_in_sms_response,
):
    # Given
    mock_country_accepts_url_in_sms.return_value = country_accepts_url_in_sms_response
    upcoming_appointment.product.practitioner.practitioner_profile.phone_number = (
        "+17733220000"
    )

    # When
    confirm_booking_sms_notifications_to_practitioner(
        upcoming_appointment.id,
        upcoming_appointment.api_id,
        {},
    )

    # Then
    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]
    expected_message_arg = "You have a new appointment on Maven*! If you cannot make it, please cancel in the MPractice iOS app."
    if country_accepts_url_in_sms_response:
        expected_message_arg = "You have a new appointment on Maven*! If you cannot make it, please cancel in the MPractice iOS app. Appt details here:*"
    assert fnmatch.fnmatch(message_arg, expected_message_arg)
    appointment_id = mock_send_sms.call_args_list[0][1]["appointment_id"]
    assert appointment_id == upcoming_appointment.id


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
@mock.patch(
    "appointments.tasks.appointment_notifications._send_sms_upcoming_appointment"
)
@mock.patch("appointments.tasks.appointment_notifications.country_accepts_url_in_sms")
def test_sms_notify_upcoming_appointments_practitioner(
    mock_country_accepts_url_in_sms,
    mock_send_sms_upcoming_appointment,
    upcoming_appointment,
    country_accepts_url_in_sms_response,
):
    # Given
    mock_country_accepts_url_in_sms.return_value = country_accepts_url_in_sms_response

    upcoming_appointment.scheduled_start = (
        datetime.datetime.utcnow() + datetime.timedelta(minutes=2)
    )
    upcoming_appointment.practitioner.practitioner_profile.phone_number = "+17733220000"

    # When
    sms_notify_upcoming_appointments_practitioner()

    # Then
    mock_send_sms_upcoming_appointment.assert_called_once()
    message_arg = mock_send_sms_upcoming_appointment.call_args.args[4]

    expected_message_arg = f"Your next Maven appointment starts in {upcoming_appointment._starts_in_minutes()} minutes! Make sure you have good WiFi."
    if country_accepts_url_in_sms_response:
        expected_message_arg = (
            f"{expected_message_arg} Review appointment details here: *"
        )
    assert fnmatch.fnmatch(message_arg, expected_message_arg)


# Basic VIP notify test - no org
def test_notify_vip_bookings_vip_no_organization():
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_notify_vip_bookings_channel:
        member = namedtuple("member", ["id", "is_enterpise", "organization"])
        member.id = 12345
        member.is_enterprise = True
        member.organization = None
        notify_vip_bookings(member, "Test Title", "This is a test message")

    mock_notify_vip_bookings_channel.assert_not_called()


# Basic VIP notify test - no org name
def test_notify_vip_bookings_vip_no_organization_name():
    with mock.patch(
        "appointments.tasks.appointment_notifications.notify_vip_bookings_channel"
    ) as mock_notify_vip_bookings_channel:
        member = namedtuple("member", ["id", "is_enterpise", "organization"])
        member.id = 12345
        member.is_enterprise = True
        member.organization = namedtuple("organization", ["name"])
        member.organization.name = None
        notify_vip_bookings(member, "Test Title", "This is a test message")

    mock_notify_vip_bookings_channel.assert_not_called()


# Test to ensure that Non-CAs get an SMS message sent for cancelled appointments
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
def test_send_practitioner_cancellation_note_no_ca(upcoming_appointment):
    with mock.patch(
        "utils.braze_events.appointment_canceled_member_to_member"
    ), mock.patch(
        "utils.braze_events.appointment_canceled_member_to_practitioner"
    ), mock.patch(
        "appointments.tasks.appointment_notifications.send_sms"
    ) as sms_mock:
        upcoming_appointment.practitioner.practitioner_profile.phone_number = (
            "1-212-555-5555"
        )
        send_practitioner_cancellation_note(upcoming_appointment.id)

    sms_mock.assert_called_once()


# Test to ensure that CAs DO NOT get an SMS message sent for cancelled appointments
@pytest.mark.parametrize("upcoming_appointment", [(False, False, True)], indirect=True)
def test_send_practitioner_cancellation_note_ca(upcoming_appointment):
    with mock.patch(
        "utils.braze_events.appointment_canceled_member_to_member"
    ), mock.patch(
        "utils.braze_events.appointment_canceled_member_to_practitioner"
    ), mock.patch(
        "appointments.tasks.appointment_notifications.send_sms"
    ) as sms_mock:
        send_practitioner_cancellation_note(upcoming_appointment.id)

    sms_mock.assert_not_called()


@pytest.fixture
def member_ack(request, factories):
    scheduled_start, confirm_message_sid = request.param
    appt = factories.AppointmentFactory.create(scheduled_start=scheduled_start)
    return factories.MemberAppointmentAckFactory.create(
        appointment=appt,
        confirm_message_sid=confirm_message_sid,
        phone_number="2025551234",
    )


@pytest.mark.parametrize(
    ["member_ack", "calls_send_sms"],
    [
        ((datetime.datetime.utcnow() + datetime.timedelta(days=8), None), False),
        ((datetime.datetime.utcnow() + datetime.timedelta(days=6), "test_sid"), False),
        ((datetime.datetime.utcnow() + datetime.timedelta(days=6), None), True),
    ],
    ids=[
        "Appointment start more than 7 days in the future",
        "Appointment start less than 7 days in the future, has confirm_message_sid",
        "Appointment start less than 7 days in the future, no confirm_message_sid",
    ],
    indirect=["member_ack"],
)
def test_schedule_member_confirm_appointment_sms(member_ack, calls_send_sms):
    with mock.patch(
        "appointments.tasks.appointment_notifications.send_sms"
    ) as sms_mock:
        result = namedtuple("Result", "_result", rename=True)
        result._result = namedtuple("SubResult", "sid")
        result._result.sid = "Test_sid"
        sms_mock.return_value = result

        schedule_member_confirm_appointment_sms()
        if calls_send_sms:
            sms_mock.assert_called()
            assert member_ack.confirm_message_sid is not None
        else:
            sms_mock.assert_not_called()


@pytest.mark.parametrize(
    ["member_ack", "should_call_cancel_sms"],
    [
        ((datetime.datetime.utcnow(), None), False),
        ((datetime.datetime.utcnow(), "123"), True),
    ],
    ids=[
        "No SMS scheduled",
        "SMS scheduled",
    ],
    indirect=["member_ack"],
)
def test_cancel_member_appointment_confirmation(member_ack, should_call_cancel_sms):
    with mock.patch(
        "appointments.tasks.appointment_notifications.cancel_sms"
    ) as cancel_sms_mock:
        cancel_member_appointment_confirmation(member_ack.appointment_id)
        if should_call_cancel_sms:
            cancel_sms_mock.assert_called_once_with(member_ack.confirm_message_sid)
        else:
            cancel_sms_mock.assert_not_called()


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("valid_timestamp", [True, False])
@pytest.mark.parametrize("upcoming_appointment", [(True, True, False)], indirect=True)
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("appointments.tasks.appointment_notifications.send_sms")
@mock.patch("l10n.utils.get_locale_from_member_preference")
@mock.patch("appointments.tasks.appointment_notifications.country_accepts_url_in_sms")
def test_schedule_member_appointment_confirmation_sms(
    mock_notifications_country_accepts_url_in_sms,
    mock_member_locale,
    mock_send_sms,
    locale,
    upcoming_appointment,
    valid_timestamp,
    country_accepts_url_in_sms_response,
    release_mono_api_localization_on,
):
    # Given
    mock_notifications_country_accepts_url_in_sms.return_value = (
        country_accepts_url_in_sms_response
    )
    mock_member_locale.return_value = locale

    if not valid_timestamp:
        upcoming_appointment.scheduled_start = (
            datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        )

    # When
    schedule_member_appointment_confirmation_sms(
        "+17733220000",
        upcoming_appointment,
        123,
    )

    # Then
    if valid_timestamp:
        mock_send_sms.assert_called_once()
        message_arg = mock_send_sms.call_args_list[0][1]["message"]
        assert message_arg != "member_24_hour_reminder_sms"
        appointment_id = mock_send_sms.call_args_list[0][1]["appointment_id"]
        assert appointment_id == upcoming_appointment.id
        assert (
            f"{current_app.config['BASE_URL']}/my-appointments" in message_arg
        ) == country_accepts_url_in_sms_response
    else:
        mock_send_sms.assert_not_called()


@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.localization_is_enabled")
@mock.patch("appointments.tasks.appointment_notifications.send_sms")
@mock.patch("l10n.utils.get_locale_from_member_preference")
def test_member_cancellation_note_message(
    mock_member_locale,
    mock_send_sms,
    mock_localization_is_enabled,
    locale,
    upcoming_appointment,
):
    mock_member_locale.return_value = locale

    # assign a phone number
    upcoming_appointment.member.member_profile.phone_number = "1-212-555-5555"

    # trigger 'send_member_cancellation_note'
    send_member_cancellation_note(upcoming_appointment.id)

    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]
    assert message_arg != "member_cancellation_note"
    # confirm that variable was populated
    assert "name" not in message_arg


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.localization_is_enabled")
@mock.patch("appointments.tasks.appointment_notifications.send_sms")
@mock.patch("l10n.utils.get_locale_from_member_preference")
@mock.patch("appointments.tasks.appointment_notifications.country_accepts_url_in_sms")
def test_sms_notify_upcoming_appointments_member(
    mock_notifications_country_accepts_url_in_sms,
    mock_member_locale,
    mock_send_sms,
    mock_localization_is_enabled,
    locale,
    upcoming_appointment,
    country_accepts_url_in_sms_response,
):
    # Given
    mock_notifications_country_accepts_url_in_sms.return_value = (
        country_accepts_url_in_sms_response
    )

    mock_member_locale.return_value = locale

    # assign a phone number
    upcoming_appointment.member.member_profile.phone_number = "1-212-555-5555"

    # update appointment start time to be within 2 minutes
    upcoming_appointment.scheduled_start = (
        datetime.datetime.utcnow() + datetime.timedelta(minutes=1)
    )

    # When
    sms_notify_upcoming_appointments_member()

    # Then
    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]
    assert message_arg != "notify_member_upcoming_appointment"
    assert "appointment_start_time_remaining" not in message_arg
    assert (
        f"{current_app.config['BASE_URL']}/my-appointments" in message_arg
    ) == country_accepts_url_in_sms_response


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("upcoming_appointment", [(False, False, False)], indirect=True)
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.localization_is_enabled")
@mock.patch("appointments.tasks.appointment_notifications.send_sms")
@mock.patch("l10n.utils.get_locale_from_member_preference")
@mock.patch("appointments.tasks.appointment_notifications.country_accepts_url_in_sms")
def test_sms_notify_member_about_new_appointment(
    mock_notifications_country_accepts_url_in_sms,
    mock_member_locale,
    mock_send_sms,
    mock_localization_is_enabled,
    locale,
    upcoming_appointment,
    country_accepts_url_in_sms_response,
):
    # Given
    mock_notifications_country_accepts_url_in_sms.return_value = (
        country_accepts_url_in_sms_response
    )
    mock_member_locale.return_value = locale

    # assign a phone number
    upcoming_appointment.member.member_profile.phone_number = "1-212-555-5555"

    # When
    sms_notify_member_about_new_appointment(appointment=upcoming_appointment)

    # Then
    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]
    assert message_arg != "sms_notify_member_about_new_appointment"
    assert (
        f"{current_app.config['BASE_URL']}/my-appointments" in message_arg
    ) == country_accepts_url_in_sms_response


@mock.patch("utils.braze_events.braze.send_event")
def test_braze_appointment_canceled_member_to_member__ca_intro(mock_braze, factories):
    # given:
    ca = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[factories.VerticalFactory.create_cx_vertical()]
    )
    appointment = factories.AppointmentFactory.create_with_practitioner(
        purpose="introduction", practitioner=ca
    )
    # when
    braze_events.appointment_canceled_member_to_member(appointment)

    # then
    assert mock_braze.called_once()
    args = mock_braze.call_args[0]
    assert args[0] == appointment.member
    assert args[1] == "appointment_canceled_member_to_member"
    assert args[2] == {
        "appointment_id": appointment.api_id,
        "is_intro_appointment": True,
        "practitioner_id": ca.id,
        "practitioner_name": appointment.practitioner.full_name,
        "practitioner_vertical_id": appointment.product.vertical_id,
        "practitioner_image": appointment.practitioner.avatar_url,
        "practitioner_type": ", ".join(
            v.name for v in appointment.practitioner.practitioner_profile.verticals
        ),
        "more_than_3_hours": False,
    }


@mock.patch("utils.braze_events.braze.send_event")
def test_braze_appointment_canceled_member_to_member__ca(mock_braze, factories):
    # given:
    ca = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[factories.VerticalFactory.create_cx_vertical()]
    )
    appointment = factories.AppointmentFactory.create_with_practitioner(
        purpose="not intro", practitioner=ca
    )
    # when
    braze_events.appointment_canceled_member_to_member(appointment)

    # then
    assert mock_braze.called_once()
    args = mock_braze.call_args[0]
    assert args[0] == appointment.member
    assert args[1] == "appointment_canceled_member_to_member"
    assert args[2] == {
        "appointment_id": appointment.api_id,
        "is_intro_appointment": False,
        "practitioner_id": ca.id,
        "practitioner_name": appointment.practitioner.full_name,
        "practitioner_vertical_id": appointment.product.vertical_id,
        "practitioner_image": appointment.practitioner.avatar_url,
        "practitioner_type": ", ".join(
            v.name for v in appointment.practitioner.practitioner_profile.verticals
        ),
        "more_than_3_hours": False,
    }


@mock.patch("utils.braze_events.braze.send_event")
def test_braze_appointment_canceled_member_to_member(mock_braze, factories):
    # given:
    appointment = factories.AppointmentFactory.create()
    # when
    braze_events.appointment_canceled_member_to_member(appointment)

    # then
    assert mock_braze.called_once()
    args = mock_braze.call_args[0]
    assert args[0] == appointment.member
    assert args[1] == "appointment_canceled_member_to_member"
    assert args[2] == {
        "appointment_id": appointment.api_id,
        "is_intro_appointment": False,
        "practitioner_id": appointment.practitioner.id,
        "practitioner_name": appointment.practitioner.full_name,
        "practitioner_vertical_id": appointment.product.vertical_id,
        "practitioner_image": appointment.practitioner.avatar_url,
        "practitioner_type": ", ".join(
            v.name for v in appointment.practitioner.practitioner_profile.verticals
        ),
        "more_than_3_hours": False,
    }


@mock.patch("utils.braze_events.braze.send_event")
def test_braze_appointment_canceled_member_to_member_cancel_more_than_3_hours(
    mock_braze, factories
):
    # given:
    appointment = factories.AppointmentFactory.create()
    appointment.scheduled_start = datetime.datetime.utcnow() + datetime.timedelta(
        hours=4
    )
    # when
    braze_events.appointment_canceled_member_to_member(appointment)

    # then
    assert mock_braze.called_once()
    args = mock_braze.call_args[0]
    assert args[0] == appointment.member
    assert args[1] == "appointment_canceled_member_to_member"
    assert args[2] == {
        "appointment_id": appointment.api_id,
        "is_intro_appointment": False,
        "practitioner_id": appointment.practitioner.id,
        "practitioner_name": appointment.practitioner.full_name,
        "practitioner_vertical_id": appointment.product.vertical_id,
        "practitioner_image": appointment.practitioner.avatar_url,
        "practitioner_type": ", ".join(
            v.name for v in appointment.practitioner.practitioner_profile.verticals
        ),
        "more_than_3_hours": True,
    }
