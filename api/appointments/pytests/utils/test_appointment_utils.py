import pytest

from appointments.utils.appointment_utils import convert_time_to_message_str


@pytest.mark.parametrize(
    "given_minute_value,expected_response",
    [(1, "1 minute"), (2, "2 minutes"), (60, "1 hour"), (120, "2 hours")],
)
def test_convert_time_to_message_str(given_minute_value, expected_response):
    res = convert_time_to_message_str(upcoming_appt_time_in_mins=given_minute_value)
    assert res == expected_response
