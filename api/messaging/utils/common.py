from __future__ import annotations

from zenpy.lib.api_objects import TicketAudit

from storage.connection import db
from utils.log import logger

log = logger(__name__)


def wallet_exists_for_channel(channel_id: int) -> bool:
    from wallet.models.reimbursement_wallet import ReimbursementWallet
    from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

    return (
        db.session.query(ReimbursementWallet.id)
        .join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id == ReimbursementWallet.id,
        )
        .filter(
            ReimbursementWalletUsers.channel_id == channel_id,
        )
        .count()
        > 0
    )


def get_wallet_by_channel_id(channel_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from wallet.models.reimbursement_wallet import ReimbursementWallet
    from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

    return (
        db.session.query(ReimbursementWallet)
        .join(
            ReimbursementWalletUsers,
            ReimbursementWalletUsers.reimbursement_wallet_id == ReimbursementWallet.id,
        )
        .filter(
            ReimbursementWalletUsers.channel_id == channel_id,
        )
        .one_or_none()
    )


def parse_comment_id_from_ticket_audit(
    ticket_audit: TicketAudit, user_id: int
) -> int | None:
    comment_ids = [
        e["id"] for e in ticket_audit.audit.events if e.get("type") == "Comment"
    ]
    if len(comment_ids) == 1:
        log.info(
            "Successfully got comment_id from ticket audit",
            user_id=user_id,
            zendesk_ticket_id=ticket_audit.ticket.id,
        )
        return comment_ids[0]
    elif len(comment_ids) > 1:
        log.error(
            "Cannot determine Zendesk comment ID from audit",
            user_id=user_id,
            comment_ids=comment_ids,
            zendesk_ticket_id=ticket_audit.ticket.id,
        )
    else:
        log.error(
            "Cannot get Zendesk comment ID from audit",
            user_id=user_id,
            zendesk_ticket_id=ticket_audit.ticket.id,
        )

    return None


def parse_ticket_comment_body_from_ticket_audit(
    ticket_audit: TicketAudit, user_id: int
) -> str | None:
    messages = [
        e["body"] for e in ticket_audit.audit.events if e.get("type") == "Comment"
    ]
    if len(messages) == 1:
        log.info(
            "Successfully got comment body from ticket audit",
            user_id=user_id,
            zendesk_ticket_id=ticket_audit.ticket.id,
        )
        return messages[0]
    elif len(messages) > 1:
        log.error(
            "Cannot determine Zendesk comment body from audit",
            user_id=user_id,
            zendesk_ticket_id=ticket_audit.ticket.id,
        )
    else:
        log.error(
            "Cannot get Zendesk comment body from audit",
            user_id=user_id,
            zendesk_ticket_id=ticket_audit.ticket.id,
        )
    return None
