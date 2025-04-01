from datetime import datetime
from typing import TYPE_CHECKING

from messaging.models.messaging import Message

if TYPE_CHECKING:
    from authn.models.user import User


def can_send_automated_message(
    user: "User",
    required_days_since_last_ca_message: int,
    required_days_since_last_member_message: int,
) -> bool:
    """
    Verifies that there have been no messages exchanged between a CA and the member(User)
    prior to creating an automated message.
    The thresholds are sent in the request body via inbound messages from Braze.
    """

    def _days_since_creation(m: Message) -> int:
        ts = datetime.utcnow()
        return (ts - m.created_at).days

    last_ca_message_to_member = Message.last_ca_message_to_member(user)
    last_member_message_to_ca = Message.last_member_message_to_ca(user)

    can_send = True

    if (
        last_ca_message_to_member
        and _days_since_creation(last_ca_message_to_member)
        < required_days_since_last_ca_message
    ) or (
        last_member_message_to_ca
        and _days_since_creation(last_member_message_to_ca)
        < required_days_since_last_member_message
    ):
        can_send = False

    return can_send
