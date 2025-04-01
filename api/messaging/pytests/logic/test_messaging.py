from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import MagicMock

from messaging.logic.messaging import can_send_automated_message
from messaging.models.messaging import Message


def test_can_send_automated_message_valid_dates():

    """
    Scenario:
        Both the last message sent from a provider
        and the last message sent from a member
        are before the threshold set in Braze; assert we can send the message.
    """
    user = MagicMock()
    member_message_days = 4
    ca_message_days = 4

    ts = datetime.utcnow() - timedelta(days=10)
    mock_last_message = MagicMock(created_at=ts)

    with mock.patch.object(
        Message, "last_ca_message_to_member", return_value=mock_last_message
    ):
        with mock.patch.object(
            Message, "last_member_message_to_ca", return_value=mock_last_message
        ):
            ret = can_send_automated_message(user, ca_message_days, member_message_days)
            assert ret


def test_can_send_automated_message_member():
    """
    Scenario:
        Member has sent a message within the time window, CA automated message should not be created.
    """
    user = MagicMock()
    days_since_last_member_message = 4
    days_since_last_ca_message = 4

    last_member_message = MagicMock(created_at=datetime.utcnow() - timedelta(days=2))
    last_ca_message = MagicMock(created_at=datetime.utcnow() - timedelta(days=10))

    with mock.patch.object(
        Message, "last_ca_message_to_member", return_value=last_ca_message
    ):
        with mock.patch.object(
            Message,
            "last_member_message_to_ca",
            return_value=last_member_message,
        ):
            ret = can_send_automated_message(
                user, days_since_last_ca_message, days_since_last_member_message
            )
            assert not ret


def test_can_send_automated_message_provider():
    """
    Scenario:
        Provider has sent message within the time window, the CA automated message should not be created.
    """
    user = MagicMock()
    days_since_last_member_message = 4
    days_since_last_ca_message = 4

    last_member_message = MagicMock(created_at=datetime.utcnow() - timedelta(days=10))
    last_ca_message = MagicMock(created_at=datetime.utcnow() - timedelta(days=2))

    with mock.patch.object(
        Message, "last_ca_message_to_member", return_value=last_ca_message
    ):
        with mock.patch.object(
            Message,
            "last_member_message_to_ca",
            return_value=last_member_message,
        ):
            ret = can_send_automated_message(
                user, days_since_last_ca_message, days_since_last_member_message
            )
            assert not ret
