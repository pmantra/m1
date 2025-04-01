import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from common.constants import Environment
from messaging.services import twilio
from messaging.services.twilio import url_mapping


@pytest.mark.parametrize(
    ["to", "msg", "send_at", "schedule_type", "status_callback"],
    [
        (
            "+15555555555",
            "test message",
            None,
            None,
            url_mapping.get(Environment.current()),
        ),
        (
            "+15555555555",
            "test message with delivery_time",
            datetime.datetime.now(),
            "fixed",
            url_mapping.get(Environment.current()),
        ),
    ],
    ids=[
        "sends message with no send_at param",
        "sends message with send_at param",
    ],
)
@mock.patch("messaging.services.twilio.log.info")
def test_send_message(mock_log_info, to, msg, send_at, schedule_type, status_callback):
    with patch(
        "messaging.services.twilio.twilio_client", autospec=True
    ) as twilio_client_mock:
        twilio.send_message(to=to, message=msg, send_at=send_at)
        twilio_client_mock.messages.create.assert_called_with(
            to=to,
            body=msg,
            send_at=send_at.strftime("%Y-%m-%dT%H:%M:%S%zZ") if send_at else None,
            schedule_type=schedule_type,
            messaging_service_sid=twilio.TWILIO_MESSAGING_SERVICE_SID,
            status_callback=status_callback,
        )
        # confirm logs not called with appointment id
        assert mock_log_info.call_args_list[0][1]["appointment_id"] is None


@mock.patch("messaging.services.twilio.log.info")
@mock.patch("messaging.services.twilio.twilio_client")
def test_send_message_with_appointment_id(mock_twilio_client, mock_log_info):
    # When:
    twilio.send_message(
        to="+15555555555",
        message="test message",
        send_at=datetime.datetime.now(),  # noqa
        appointment_id=123,
    )
    # Then:
    appointment_id = mock_log_info.call_args_list[0][1]["appointment_id"]
    assert appointment_id == 123
    message_arg = mock_log_info.call_args_list[0][0][0]
    assert message_arg == "SMS message sent"


def test_cancel_message():
    sid = "123456"
    with patch(
        "messaging.services.twilio.twilio_client", autospec=True
    ) as twilio_client_mock:
        twilio.cancel_message(sid)
        twilio_client_mock.messages(sid).update.assert_called_with(status="canceled")
