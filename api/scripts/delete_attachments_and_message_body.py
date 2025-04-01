from typing import List

from messaging.models.messaging import Message
from storage.connection import db


def delete_attachments_and_message_body(message_ids: List[str]) -> None:
    attachments = []
    print("checking messages")  # noqa
    for m_id in message_ids:
        m = Message.query.get(m_id)
        print(f"removing body for message {m.id}")  # noqa

        m.body = "(This message has been removed.)"
        db.session.add(m)
        db.session.commit()
        print(f"message attachments: {m.attachments}")  # noqa
        attachments.append(m.attachments[0].id)
    for a_id in attachments:
        print(f"deleting attachment {a_id} from the DB")  # noqa
        db.session.execute(
            f"delete from user_asset_message where user_asset_id={a_id};"
        )
        db.session.execute(f"delete from user_asset where id={a_id};")
        db.session.commit()
    print(  # noqa
        "Message attachments are deleted. Don't forget to make a CPFR ticket for infra to delete the image assets from the GCP bucket"
    )
    print(f"Assets: {attachments}")  # noqa
