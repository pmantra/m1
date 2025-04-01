from datetime import datetime, timedelta

import pytest

from messaging.models.messaging import Message, MessageCredit
from storage.connection import db


@pytest.fixture()
def messages_with_credits(message_channel):
    messages = []

    for _ in range(3):
        ts = datetime.utcnow()
        message = Message(
            channel_id=message_channel.id,
            user=message_channel.member,
            credit=MessageCredit(
                responded_at=ts, respond_by=ts, user=message_channel.member
            ),
        )
        messages.append(message)

    db.session.add_all(messages)

    db.session.commit()


@pytest.mark.parametrize(
    "refunded_at, respond_by, expected",
    [
        # Invalid cases
        (None, None, False),  # no respond by date
        (
            None,
            datetime.utcnow() + timedelta(hours=2),
            False,
        ),  # respond by is in the future
        (datetime.utcnow(), None, False),  # already refunded
        # Valid cases
        (
            None,
            datetime.utcnow() - timedelta(hours=2),
            True,
        ),  # has not refunded and respond by is in the past
    ],
)
def test_is_eligible_for_refund(refunded_at, respond_by, expected, default_user):
    mc = MessageCredit(
        user=default_user,
        refunded_at=refunded_at,
        respond_by=respond_by,
    )
    assert mc.is_eligible_for_refund() is expected
