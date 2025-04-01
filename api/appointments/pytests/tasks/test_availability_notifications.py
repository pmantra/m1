import datetime
import fnmatch
from unittest import mock

import pytest

from appointments.tasks.availability_notifications import notify_about_availability


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@mock.patch("appointments.tasks.availability_notifications.country_accepts_url_in_sms")
@mock.patch("appointments.tasks.availability_notifications.send_sms")
def test_notify_about_availability(
    mock_send_sms,
    mock_country_accepts_url_in_sms,
    country_accepts_url_in_sms_response,
    availability_notification_req,
):

    # Given
    mock_country_accepts_url_in_sms.return_value = country_accepts_url_in_sms_response
    request_dt = datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30)
    avail_req, channel = availability_notification_req(request_dt)
    prac_id = avail_req.practitioner_id
    avail_req.member.member_profile.phone_number = "+17733220000"

    # When
    notify_about_availability(prac_id)

    # Then
    expected_message_arg = f"Great news! {avail_req.practitioner.full_name} has added new availability for appointments on Maven!"
    if country_accepts_url_in_sms_response:
        expected_message_arg = (
            expected_message_arg
            + " To view available times and book, please head here: *"
        )
    else:
        expected_message_arg = (
            expected_message_arg
            + " To view available times and book, please head to the Maven application."
        )

    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]

    assert fnmatch.fnmatch(message_arg, expected_message_arg)
