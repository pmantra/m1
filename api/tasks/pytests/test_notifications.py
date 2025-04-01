from types import SimpleNamespace
from unittest.mock import patch

from pytests.factories import MemberFactory
from tasks.notifications import _deliver_sms


class TestNotifications:
    def test_deliver_sms(self):
        user = MemberFactory()
        with patch(
            "tasks.notifications.send_sms",
            return_value=SimpleNamespace(is_blocked=False, is_ok=True),
        ) as send_mock:
            _deliver_sms(
                user_profile=user.member_profile,
                message_body="test message",
                log_props={},
            )
            send_mock.assert_called_once_with(
                message="test message",
                to_phone_number=user.member_profile.phone_number,
                user_id=user.id,
                notification_type="messaging",
            )
