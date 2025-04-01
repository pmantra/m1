from datetime import timedelta

from messaging.models.messaging import Message, MessageCredit
from models.profiles import PractitionerProfile
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def allot_message_credit_for_existing_free_messages():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Migrate the existing free messages to have a corresponding message_credit
    :return:
    """
    free_message_without_credit = (
        db.session.query(Message)
        .outerjoin(MessageCredit, Message.id == MessageCredit.message_id)
        .outerjoin(PractitionerProfile, Message.user_id == PractitionerProfile.user_id)
        .filter(MessageCredit.id.is_(None), PractitionerProfile.user_id.is_(None))
        .all()
    )

    log.debug("Got %s free messages without credit", len(free_message_without_credit))
    for message in free_message_without_credit:
        channel = message.channel
        ch_msgs = sorted(channel.messages, key=lambda m: m.created_at)

        assert ch_msgs[0] == message  # first message is free

        # filter out own messages
        ch_msgs = [m for m in ch_msgs if m.user_id != message.user_id]

        if len(ch_msgs) > 0:
            # then the first one is the response
            responded_at = ch_msgs[0].created_at
            response_id = ch_msgs[0].id
        else:
            responded_at = None
            response_id = None

        profile = PractitionerProfile.query.get(channel.practitioner.id)
        respond_by = message.created_at + timedelta(hours=profile.response_time or 24)

        MessageCredit.create(
            count=1,
            user_id=message.user_id,
            message_id=message.id,
            respond_by=respond_by,
            responded_at=responded_at,
            response_id=response_id,
            json={"free": True},
        )

        db.session.commit()
        log.debug("%s created", message.credit)
