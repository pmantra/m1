import datetime
from unittest import mock

import pytest

from appointments.models.member_appointment import MemberAppointmentAck
from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.services.acknowledgement import (
    _acknowledge_appointment_for_member,
    _acknowledge_appointment_for_practitioner,
    update_member_appointment_ack_sent,
)
from pytests import freezegun


@pytest.fixture
def member_appointment_ack(factories):
    appt = factories.AppointmentFactory.create(
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(days=1)
    )
    return factories.MemberAppointmentAckFactory.create(
        phone_number="2025555555",
        is_acked=False,
        appointment=appt,
    )


@pytest.fixture
def practitioner_appointment_ack(factories):
    appt = factories.AppointmentFactory.create(
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(days=1)
    )
    return factories.PractitionerAppointmentAckFactory.create(
        ack_by=datetime.datetime.utcnow() + datetime.timedelta(days=2),
        warn_by=datetime.datetime.utcnow() - datetime.timedelta(days=3),
        phone_number="2025555555",
        is_acked=False,
        appointment=appt,
    )


@pytest.mark.parametrize(
    ["phone_number", "sid", "body", "expected_message", "expected_ack"],
    [
        ("2025554444", "test_sid", "Y", None, False),
        (
            "2025555555",
            "test_sid",
            "X",
            "This is an automated message. For help with rebooking or other questions, message us in the Maven app.",
            False,
        ),
        ("2025555555", "test_sid", "Y", "Thank you! We'll see you soon.", True),
        ("2025555555", "test_sid", "yEs", "Thank you! We'll see you soon.", True),
    ],
    ids=[
        "no MemberAppointmentAck found",
        "MemberAppointmentAck found response not in allowed responses",
        "MemberAppointmentAck found response in allowed responses",
        "MemberAppointmentAck found response in allowed responses, not exact match",
    ],
)
def test_acknowledge_appointment_for_member(
    member_appointment_ack,
    phone_number,
    sid,
    body,
    expected_message,
    expected_ack,
    default_user,
    factories,
):
    user = factories.DefaultUserFactory()
    factories.MemberProfileFactory.create(phone_number=phone_number, user_id=user.id)
    result = _acknowledge_appointment_for_member(phone_number, sid, body)
    assert result == expected_message
    if expected_ack:
        ack = MemberAppointmentAck.query.get(member_appointment_ack.id)
        assert ack.reply_message_sid == sid
        assert ack.is_acked is True
        assert ack.ack_date is not None


@mock.patch("appointments.services.acknowledgement.log.warning")
def test_acknowledge_appointment_for_member__multiple_results_found(
    mock_log,
    member_appointment_ack,
    default_user,
    factories,
):

    # Given
    phone_number = "2025555555"
    sid = "test_sid"
    body = "Y"

    # create two distinct users with the same phone number in their MemberProfile
    user_1 = factories.DefaultUserFactory()
    user_2 = factories.DefaultUserFactory()

    factories.MemberProfileFactory.create(phone_number=phone_number, user_id=user_1.id)
    factories.MemberProfileFactory.create(phone_number=phone_number, user_id=user_2.id)

    # When
    result = _acknowledge_appointment_for_member(phone_number, sid, body)

    # Then
    assert result == "Thank you! We'll see you soon."
    mock_log.assert_called()
    assert (
        "Multiple results found for user id and phone number. Returning the most recent result"
        in mock_log.call_args[0][0]
    )


@pytest.mark.parametrize(
    ["locale", "body", "expected_message"],
    [
        (
            "en",
            "X",
            "member_confirm_invalid_response",
        ),
        ("en", "Y", "member_confirm_response"),
        ("es", "X", "member_confirm_invalid_response"),
        ("es", "Y", "member_confirm_response"),
        ("fr", "X", "member_confirm_invalid_response"),
        ("fr", "Y", "member_confirm_response"),
    ],
)
@mock.patch("l10n.utils.get_locale_from_member_preference")
def test_acknowledge_appointment_for_member__localization(
    mock_get_locale,
    locale,
    body,
    expected_message,
    release_mono_api_localization_on,
    member_appointment_ack,
    default_user,
    factories,
):
    # Given
    mock_get_locale.return_value = locale
    member_profile = factories.MemberProfileFactory.create(user=default_user)
    member_profile.phone_number = "2025555555"

    # when
    result = _acknowledge_appointment_for_member("2025555555", "test_sid", body)
    # then
    assert result != expected_message


@pytest.mark.parametrize(
    ["locale", "body", "expected_message"],
    [
        (
            "en",
            "Y",
            "provider_confirm_response",
        ),
        (
            "en",
            "n",
            "provider_confirm_invalid_response",
        ),
        ("es", "Y", "provider_confirm_response"),
        ("es", "N", "provider_confirm_invalid_response"),
        ("fr", "Y", "provider_confirm_response"),
        ("fr", "N", "provider_confirm_invalid_response"),
    ],
)
@mock.patch("l10n.utils.get_locale_from_member_preference")
def test_acknowledge_appointment_for_practitioner__localization(
    mock_get_locale,
    locale,
    body,
    expected_message,
    release_mono_api_localization_on,
    practitioner_appointment_ack,
):
    mock_get_locale.return_value = locale
    result = _acknowledge_appointment_for_practitioner("2025555555", "test_sid", body)
    assert result != expected_message


@pytest.mark.parametrize(
    ["phone_number", "sid", "body", "expected_message", "expected_ack"],
    [
        ("2025554444", "test_sid", "Y", "", False),
        (
            "2025555555",
            "test_sid",
            "X",
            "provider_confirm_invalid_response",
            False,
        ),
        (
            "2025555555",
            "test_sid",
            "okay",
            "provider_confirm_invalid_response",
            False,
        ),
        (
            "2025555555",
            "test_sid",
            "Y",
            "provider_confirm_response",
            True,
        ),
        (
            "2025555555",
            "test_sid",
            "yEs",
            "provider_confirm_response",
            True,
        ),
    ],
)
def test_acknowledge_appointment_for_practitioner(
    practitioner_appointment_ack,
    phone_number,
    sid,
    body,
    expected_message,
    expected_ack,
):
    result = _acknowledge_appointment_for_practitioner(phone_number, sid, body)
    assert result != expected_message
    if expected_ack:
        ack = PractitionerAppointmentAck.query.get(practitioner_appointment_ack.id)
        assert ack.is_acked is True


def test_acknowledge_appointment_for_practitioner__ack_by_passed(factories):
    phone_number = "2025554444"
    appt = factories.AppointmentFactory.create(
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(days=1)
    )
    factories.PractitionerAppointmentAckFactory.create(
        ack_by=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        warn_by=datetime.datetime.utcnow() - datetime.timedelta(days=3),
        phone_number=phone_number,
        is_acked=False,
        appointment=appt,
    )
    result = _acknowledge_appointment_for_practitioner(phone_number, "test_sid", "Y")
    assert result is None


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_update_member_appointment_ack_sent(member_appointment_ack):
    update_member_appointment_ack_sent(member_appointment_ack.confirm_message_sid)
    ack = MemberAppointmentAck.query.get(member_appointment_ack.id)
    assert ack.sms_sent_at == datetime.datetime.utcnow()
