from messaging.models.messaging import Channel
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def migrate_zendesk_ticket_ids():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        cc = Channel.query.filter(
            Channel.comment.contains("internal_zendesk_ticket_id")
        ).all()
        log.info(
            "Migrating zendesk_ticket_id from %d channels to the profile of the member participant.",
            len(cc),
        )
        for c in cc:
            if "internal_zendesk_ticket_id" not in c.comment:
                log.warn(
                    "Channel %s does not have a recorded internal_zendesk_ticket_id.", c
                )
                continue
            zid = c.comment.pop("internal_zendesk_ticket_id")
            member = c.member
            if not member.is_member:
                log.warn(
                    "Cannot migrate internal_zendesk_ticket_id from channel %s with no participating member.",
                    c,
                )
                continue
            p = member.member_profile
            p.zendesk_ticket_id = zid
            log.debug(
                "Moved zendesk_ticket_id %d from channel %s to member profile %s.",
                zid,
                c,
                p,
            )
    except Exception as e:
        log.exception(e)
        db.session.remove()
    db.session.commit()
    log.info("All done.")
