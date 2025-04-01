from authn.models.user import User
from data_admin.maker_base import _MakerBase
from messaging.models.messaging import Channel, Message, MessageCredit
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class MessageMaker(_MakerBase):
    def add_message(self, author, recipient, body="Hello", **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not author:
            log.warning("Cannot add message without an author!")
            return

        channel = kwargs.get(
            "channel", Channel.get_or_create_channel(author, [recipient])
        )
        if not recipient or not channel:
            log.warning("Cannot create message without an recipient!")
            return

        message = Message(
            user=author,
            body=body,
            channel_id=channel.id,
            status=kwargs.get("status", True),
        )
        db.session.add(message)
        db.session.flush()
        return message

    def create_object(self, spec, parent=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        author = User.query.filter_by(email=spec.get("author")).one()
        recipient = User.query.filter_by(email=spec.get("recipient")).one()

        message = self.add_message(author, recipient, body=spec.get("body"))
        if spec.get("free") or spec.get("paid"):
            json = {"free": True} if spec.get("free") else None
            MessageCredit.create(
                count=1,
                user_id=message.user_id,
                message_id=message.id,
                respond_by=24,
                json=json,
            )
        return message
