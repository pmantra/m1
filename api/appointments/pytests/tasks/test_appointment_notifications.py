import datetime
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

import pytest
from flask import current_app

import appointments.tasks.appointment_notifications as appointment_notifications
from appointments.models.member_appointment import MemberAppointmentAck
from messaging.services.twilio import SMSDeliveryResult
from models.common import PrivilegeType
from pytests import freezegun


@pytest.fixture
@freezegun.freeze_time(datetime.date.today())
def appointment(request, factories):
    scheduled_start_delta, json, vertical_name, privilege_type, has_ack = request.param
    vertical = factories.VerticalFactory.create(name=vertical_name or "Test")
    product = factories.ProductFactory.create(vertical=vertical)
    delta = scheduled_start_delta or datetime.timedelta(0)
    appt = factories.AppointmentFactory.create(
        scheduled_start=datetime.datetime.utcnow() + delta,
        json=json,
        product=product,
        privilege_type=privilege_type or PrivilegeType.ANONYMOUS,
    )
    appt.member.member_profile.phone_number = "2025555555"
    if has_ack:
        factories.MemberAppointmentAckFactory.create(
            appointment=appt,
            phone_number="2025555555",
            is_acked=False,
        )
    return appt


@pytest.fixture
def member_appointment_ack(request, appointment):
    sid = request.param
    return MemberAppointmentAck(
        appointment=appointment,
        phone_number=appointment.member.member_profile.phone_number,
        user=appointment.member,
        confirm_message_sid=sid,
        is_acked=False,
    )


@pytest.mark.parametrize(
    [
        "appointment",
        "send_sms_return_value",
        "member_appointment_ack",
        "expects_ack_created",
        "feature_flag_value",
    ],
    [
        (
            (
                -datetime.timedelta(minutes=59),
                None,
                None,
                None,
                None,
            ),
            None,
            None,
            False,
            True,
        ),
        (
            (
                -datetime.timedelta(hours=23),
                None,
                None,
                None,
                None,
            ),
            None,
            None,
            False,
            True,
        ),
        (
            (
                datetime.timedelta(days=9),
                None,
                None,
                None,
                False,
            ),
            None,
            None,
            True,
            True,
        ),
        (
            (
                datetime.timedelta(hours=25),
                None,
                None,
                None,
                False,
            ),
            SMSDeliveryResult(
                SimpleNamespace(
                    sid="test_sid",
                    to="5555555555",
                    error_code=None,
                    error_message=None,
                    is_ok=True,
                    is_blocked=False,
                    status="sent",
                ),
                is_ok=True,
            ),
            ("test_sid"),
            True,
            True,
        ),
        (
            (
                datetime.timedelta(days=9),
                None,
                None,
                None,
                False,
            ),
            None,
            None,
            False,
            False,
        ),
    ],
    ids=[
        "appointment with scheduled_start less than 1 hours",
        "appointment with scheduled_start less than 24 hours",
        "appointment with scheduled_start greater than 8 days",
        "appointment with scheduled_start greater than 24 hours, less than a week and sent sms message",
        "appointment with scheduled_start greater than 8 days and feature flag off",
    ],
    indirect=["appointment", "member_appointment_ack"],
)
@freezegun.freeze_time(datetime.date.today())
def test_schedule_member_appointment_confirmation(
    appointment,
    send_sms_return_value,
    member_appointment_ack,
    expects_ack_created,
    feature_flag_value,
):
    with patch(
        "appointments.tasks.appointment_notifications.send_sms", autospec=True
    ) as send_sms_mock, patch(
        "appointments.tasks.appointment_notifications.feature_flags.bool_variation",
        return_value=feature_flag_value,
    ), patch(
        "appointments.tasks.appointment_notifications.appointment_meets_pilot_criteria",
        return_value=True,
    ):
        send_sms_mock.return_value = send_sms_return_value

        result = appointment_notifications.schedule_member_appointment_confirmation(
            appointment.id
        )
        if not expects_ack_created:
            assert result is None
        else:
            assert result.phone_number == member_appointment_ack.phone_number
            assert result.appointment == member_appointment_ack.appointment
            assert (
                result.confirm_message_sid == member_appointment_ack.confirm_message_sid
            )
            assert result.is_acked is False

        if send_sms_return_value is None:
            send_sms_mock.assert_not_called()
        else:
            send_sms_mock.assert_called_once()
            appointment_id = send_sms_mock.call_args_list[0][1]["appointment_id"]
            assert appointment_id == appointment.id


@pytest.mark.parametrize(
    "vertical_name",
    ["Care Advocate", "OB-GYN", "Pediatrician", "Mental Health Provider"],
)
@pytest.mark.parametrize("feature_flag_value", [True, False])
@mock.patch("appointments.tasks.appointment_notifications.feature_flags.bool_variation")
@mock.patch("appointments.tasks.appointment_notifications.send_sms")
def test_schedule_member_appointment_confirmation__pilot_criteria(
    mock_send_sms,
    mock_feature_flag,
    vertical_name,
    feature_flag_value,
    factories,
):
    # Given
    mock_send_sms.return_value = SMSDeliveryResult(
        SimpleNamespace(
            sid="test_sid",
            to="9139526777",
            error_code=None,
            error_message=None,
            is_ok=True,
            status="sent",
        ),
        is_ok=True,
    )
    appointment = factories.AppointmentFactory.create(
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(hours=25)
    )
    appointment.member.member_profile.phone_number = "9139526777"
    mock_feature_flag.return_value = feature_flag_value
    appointment.product.vertical.name = vertical_name
    # When
    response = appointment_notifications.schedule_member_appointment_confirmation(
        appointment.id
    )
    # Then
    if feature_flag_value:
        assert response is not None
    else:
        assert response is None


@pytest.mark.parametrize(
    [
        "appointment",
        "expected_result",
    ],
    [
        (
            (None, None, "NOT_ALLOWED", PrivilegeType.STANDARD, False),
            False,
        ),
        (
            (None, None, "OBG-YN", PrivilegeType.EDUCATION_ONLY, False),
            False,
        ),
        (
            (None, None, "Mental Health Provider", PrivilegeType.STANDARD, False),
            True,
        ),
    ],
    ids=[
        "appointment not in vertical",
        "appointment in vertical but not in-state match",
        "appointment in vertical and in-state match",
    ],
    indirect=["appointment"],
)
@freezegun.freeze_time(datetime.date.today())
def test_appointment_meets_pilot_criteria(appointment, expected_result):
    result = appointment_notifications.appointment_meets_pilot_criteria(appointment)

    assert result == expected_result


@pytest.mark.parametrize(
    [
        "appointment",
        "send_sms_result",
        "called_send_sms",
    ],
    [
        (
            (
                -datetime.timedelta(hours=2),
                None,
                None,
                None,
                False,
            ),
            None,
            False,
        ),
        (
            (
                datetime.timedelta(minutes=55),
                {"notified_60m_sms": "any"},
                None,
                None,
                False,
            ),
            None,
            False,
        ),
        (
            (
                datetime.timedelta(minutes=55),
                None,
                "Mental Health Provider",
                PrivilegeType.STANDARD,
                False,
            ),
            SMSDeliveryResult(
                SimpleNamespace(
                    sid="test_sid",
                    to="5555555555",
                    error_code=None,
                    error_message=None,
                    is_ok=True,
                    is_blocked=False,
                    status="sent",
                ),
                is_ok=True,
            ),
            True,
        ),
    ],
    ids=[
        "no appointments staring between 50-60 minutes from now",
        "appointment already notified",
        "appointment member gets sms",
    ],
    indirect=["appointment"],
)
@pytest.mark.parametrize("bool_variation", [True, False])
@mock.patch("utils.braze_events.appointment_reminder_member")
@mock.patch(
    "appointments.tasks.appointment_notifications.handle_push_notifications_for_1_hour_reminder"
)
@mock.patch("appointments.tasks.appointment_notifications.feature_flags.bool_variation")
@freezegun.freeze_time(datetime.date.today())
def test_sms_notify_how_to_launch(
    mock_feature_flag,
    mock_handle_push_notifications_for_1_hour_reminder,
    mock_braze_event,
    bool_variation,
    appointment,
    send_sms_result,
    called_send_sms,
    request,
):
    # Given
    mock_feature_flag.return_value = bool_variation

    test_id = request.node.name
    # follows the old code path, which only assigns 'notified:sms:how_to_launch' to the appointment json
    if "appointment already notified" in test_id and bool_variation is False:
        appointment.json["notified:sms:how_to_launch"] = "any"

    # When/ Then
    with patch(
        "appointments.tasks.appointment_notifications.send_sms",
        autospec=True,
        return_value=send_sms_result,
    ) as send_sms_mock:
        appointment_notifications.sms_notify_how_to_launch()
        if called_send_sms:
            send_sms_mock.assert_called_once()
            mock_braze_event.assert_called_once()
        else:
            send_sms_mock.assert_not_called()
            mock_braze_event.assert_not_called()


@pytest.mark.parametrize(
    [
        "appointment",
    ],
    [
        (
            (
                datetime.timedelta(minutes=55),
                None,
                "Mental Health Provider",
                PrivilegeType.STANDARD,
                False,
            ),
        ),
    ],
    indirect=["appointment"],
)
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.get_locale_from_member_preference")
@freezegun.freeze_time(datetime.date.today())
def test_sms_notify_how_to_launch_localization__old_path(
    mock_get_locale, locale, appointment, release_mono_api_localization_on
):
    # Given
    mock_get_locale.return_value = locale
    # When:
    with patch(
        "appointments.tasks.appointment_notifications.send_sms",
        autospec=True,
    ) as send_sms_mock:
        appointment_notifications.sms_notify_how_to_launch()
        # Then:
        result = {
            "en": "how_to_launch_notif_old_path",
            "es": "how_to_launch_notif_old_path",
            "fr": "how_to_launch_notif_old_path",
            "fr_CA": "how_to_launch_notif_old_path",
        }
        send_sms_mock.assert_called()
        assert send_sms_mock.call_args_list[0][1]["message"] != result[locale]
        assert (
            send_sms_mock.call_args_list[0][1]["to_phone_number"]
            == "tel:+1-202-555-5555"
        )
        assert send_sms_mock.call_args_list[0][1]["user_id"] == appointment.member.id
        assert send_sms_mock.call_args_list[0][1]["notification_type"] == "appointments"
        assert send_sms_mock.call_args_list[0][1]["appointment_id"] == appointment.id


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize(
    "reminder_minutes_before_start,expected_response",
    [(1, "1 minute"), (2, "2 minutes"), (60, "1 hour"), (120, "2 hours")],
)
@pytest.mark.parametrize(
    [
        "appointment",
    ],
    [
        (
            (
                datetime.timedelta(minutes=55),
                None,
                "Mental Health Provider",
                PrivilegeType.STANDARD,
                False,
            ),
        ),
    ],
    indirect=["appointment"],
)
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("appointments.tasks.appointment_notifications.feature_flags.int_variation")
@mock.patch("l10n.utils.get_locale_from_member_preference")
@mock.patch("appointments.tasks.appointment_notifications.country_accepts_url_in_sms")
@mock.patch("appointments.tasks.appointment_notifications.feature_flags.bool_variation")
@freezegun.freeze_time(datetime.date.today())
def test_sms_notify_how_to_launch_localization__new_path(
    mock_feature_flag_bool_variation,
    mock_country_accepts_url_in_sms,
    mock_get_locale,
    mock_feature_flag_int_variation,
    locale,
    appointment,
    release_mono_api_localization_on,
    reminder_minutes_before_start,
    expected_response,
    country_accepts_url_in_sms_response,
):
    # Given
    mock_get_locale.return_value = locale
    mock_country_accepts_url_in_sms.return_value = country_accepts_url_in_sms_response
    mock_feature_flag_int_variation.return_value = reminder_minutes_before_start

    # adjust scheduled start to align with search window
    appointment.scheduled_start = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=reminder_minutes_before_start - 5
    )

    # When:
    with patch(
        "appointments.tasks.appointment_notifications.send_sms",
        autospec=True,
    ) as send_sms_mock:
        appointment_notifications.sms_notify_how_to_launch()
        # Then:
        result = {
            "en": "how_to_launch_notif_new_path",
            "es": "how_to_launch_notif_new_path",
            "fr": "how_to_launch_notif_new_path",
            "fr_CA": "how_to_launch_notif_new_path",
        }
        send_sms_mock.assert_called()
        assert send_sms_mock.call_args_list[0][1]["message"] != result[locale]
        assert (
            send_sms_mock.call_args_list[0][1]["to_phone_number"]
            == "tel:+1-202-555-5555"
        )
        assert send_sms_mock.call_args_list[0][1]["user_id"] == appointment.member.id
        assert send_sms_mock.call_args_list[0][1]["notification_type"] == "appointments"
        assert send_sms_mock.call_args_list[0][1]["appointment_id"] == appointment.id
        assert (
            f"{current_app.config['BASE_URL']}/my-appointments"
            in send_sms_mock.call_args_list[0][1]["message"]
        ) == country_accepts_url_in_sms_response
        assert expected_response in send_sms_mock.call_args_list[0][1]["message"]


@pytest.mark.parametrize(
    [
        "appointment",
    ],
    [
        (
            (
                datetime.timedelta(minutes=55),
                None,
                "Mental Health Provider",
                PrivilegeType.STANDARD,
                False,
            ),
        ),
    ],
    indirect=["appointment"],
)
@mock.patch("utils.braze_events.appointment_reminder_member")
def test_handle_push_notifications_for_1_hour_reminder(mock_braze_event, appointment):

    # Given
    now = datetime.datetime.utcnow()

    # 3-hr upcoming appointment reminder already sent
    appointment.json = {"notified_180m_sms": "any"}
    appointment.scheduled_start = now + datetime.timedelta(minutes=55)

    # When
    appointment_notifications.handle_push_notifications_for_1_hour_reminder()

    # Then
    mock_braze_event.assert_called_once()
