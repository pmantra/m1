from __future__ import annotations

import json
from traceback import format_exc

from maven import feature_flags
from zenpy.lib.api_objects import Comment, Ticket, TicketAudit

from authn.models.user import User
from messaging.models.messaging import Channel, ChannelUsers, Message
from messaging.services.zendesk import (
    get_or_create_zenpy_user,
    send_general_ticket_to_zendesk,
    zenpy_client,
)
from messaging.utils.common import (
    parse_comment_id_from_ticket_audit,
    parse_ticket_comment_body_from_ticket_audit,
)
from models.enterprise import Organization
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)


def enable_creating_reimbursement_message_to_db() -> bool:
    return feature_flags.bool_variation(
        "enable-creating-reimbursement-message-to-db",
        default=False,
    )


def get_or_create_rwu_channel(
    reimbursement_wallet_user: ReimbursementWalletUsers,
) -> Channel:
    """
    Returns the channel for the ReimbursementWalletUser (RWU) if it exists.
    Creates a channel, affiliates the channel with the RWU, and persists the
    update if the channel doesn't already exist.
    """
    if reimbursement_wallet_user.channel_id is not None:
        return (
            db.session.query(Channel)
            .filter(Channel.id == reimbursement_wallet_user.channel_id)
            .one()
        )

    channel = Channel(
        name="Maven Wallet",
        internal=True,
        comment={"user_ids": reimbursement_wallet_user.user_id},
    )

    channel_user = ChannelUsers(
        channel=channel,
        user_id=reimbursement_wallet_user.user_id,
        is_initiator=False,
        max_chars=Message.MAX_CHARS,
    )
    db.session.add(channel_user)
    log.info("Creating Wallet Channel", user_id=str(reimbursement_wallet_user.user_id))
    db.session.flush()
    reimbursement_wallet_user.channel_id = channel.id
    db.session.add(reimbursement_wallet_user)
    db.session.commit()
    return channel


def open_zendesk_ticket(
    reimbursement_wallet_user: ReimbursementWalletUsers,
    user_need_when_solving_ticket: str | None = None,
    content: str | None = None,
    called_by: str | None = None,
    additional_tags: list[str] | None = None,
) -> int:
    """
    Creates and persists a Zendesk ticket for the Reimbursement Wallet User if it
    does not already exist. Returns the id of the Zendesk ticket.
    """
    if reimbursement_wallet_user.zendesk_ticket_id is None:
        tags = [
            f"cx_channel_id_{reimbursement_wallet_user.channel_id}",
            "maven_wallet",
            "cx_messaging",
            "enterprise",
        ] + (additional_tags or [])
        organization_tag = get_organization_tag(reimbursement_wallet_user)
        if organization_tag:
            tags.append(organization_tag)
        return _generate_zendesk_ticket(
            reimbursement_wallet_user=reimbursement_wallet_user,
            ticket_subject=f"New Wallet for {reimbursement_wallet_user.member.full_name}",
            content=content or "Empty",
            tags=tags,
            status="solved",
            user_need_when_solving_ticket=user_need_when_solving_ticket
            or "customer-need-member-wallet-application-setting-up-wallet",
            called_by=called_by,
        )
    return reimbursement_wallet_user.zendesk_ticket_id


def add_reimbursement_request_comment(
    reimbursement_request: ReimbursementRequest,
    reimbursement_wallet_user: ReimbursementWalletUsers,
) -> None:
    try:
        # Open a Zendesk ticket for the user if it does not already exist.
        # In the wallet qualification workflow, we do not create a Zendesk ticket
        # by default for a new QUALIFIED or DISQUALIFIED ReimbursementWallet.
        open_zendesk_ticket(
            reimbursement_wallet_user, called_by="reimbursement request creation flow"
        )

        # attempt to retrieve existing wallet ticket
        ticket = zenpy_client.get_ticket(
            reimbursement_wallet_user.zendesk_ticket_id,
            reimbursement_wallet_user.user_id,
        )

        data = json.dumps(
            {
                "reimbursement_request_id": str(reimbursement_request.id),
                "reimbursement_wallet_id": str(
                    reimbursement_request.reimbursement_wallet_id
                ),
                "reimbursement_description": reimbursement_request.description,
                "submitter_id": str(reimbursement_wallet_user.user_id),
                "admin_link": f"https://admin.mvnapp.net/admin/reimbursementrequest/details/?id={reimbursement_request.id}",
            }
        )

        reimbursement_request_internal_comment_body = (
            f"New Reimbursement Request: \n{data}"
        )
        public_comment_body = f"Reimbursement request for {reimbursement_request.formatted_label} has been created with the id: {reimbursement_request.id}."
        called_by = "reimbursement request creation flow"

        # update the existing ticket if available and not closed
        # otherwise, create a new ticket and link it with the existing thread
        if ticket:
            try:
                requester_zendesk_user_id = get_or_create_zenpy_user(
                    reimbursement_wallet_user.member
                ).id
            except Exception:
                raise ValueError(
                    "Cannot update ticket to ZenDesk because cannot get or create zenpy user",
                )

            if ticket.status == "closed":

                log.info(
                    "Did not find an open ticket, creating new ticket for reimbursement request",
                    reimbursement_request_id=str(reimbursement_request.id),
                )

                new_ticket_id = _generate_zendesk_ticket(
                    reimbursement_wallet_user=reimbursement_wallet_user,
                    status="open",
                    ticket_subject=f"Maven Wallet message with {reimbursement_wallet_user.member.full_name}",
                    content="Empty",
                    tags=ticket.tags,
                    called_by=called_by,
                    via_followup_source_id=ticket.id,
                )

                log.info(
                    "Created new ticket",
                    old_ticket=str(ticket.id),
                    new_ticket=str(new_ticket_id),
                    user_id=str(reimbursement_wallet_user.user_id),
                )

                new_ticket = zenpy_client.get_ticket(
                    new_ticket_id,
                    reimbursement_wallet_user.user_id,
                )
                if new_ticket:
                    log.info(
                        "New ticket found",
                        ticket_id=str(ticket.id),
                        user_id=str(reimbursement_wallet_user.user_id),
                    )

                    ticket = new_ticket
                else:
                    log.error(
                        "Failed to get the new wallet ticket",
                        new_ticket=str(new_ticket_id),
                        user_id=str(reimbursement_wallet_user.user_id),
                    )
                    raise Exception(
                        "Failed to add the public facing comment due to failing to get the wallet ticket"
                    )

            else:
                log.info(
                    "Found existing ticket, updating it",
                    ticket=str(ticket.id),
                    user_id=str(reimbursement_wallet_user.user_id),
                )

            # The reimbursement request comment should be internal only
            add_comment_to_ticket(
                ticket=ticket,
                comment_body=reimbursement_request_internal_comment_body,
                author_id=requester_zendesk_user_id,
                is_public=False,
                called_by=called_by,
                reimbursement_wallet_user=reimbursement_wallet_user,
            )
            log.info(
                "Added reimbursement request comment to wallet zendesk ticket",
                ticket_id=str(ticket.id),
                user_id=str(reimbursement_wallet_user.user_id),
                reimbursement_request_id=str(reimbursement_request.id),
                wallet_id=str(reimbursement_wallet_user.reimbursement_wallet_id),
            )

            # Add a public facing comment in addition to the private comment to ops
            ticket_audit_response = add_comment_to_ticket(
                ticket=ticket,
                comment_body=public_comment_body,
                author_id=requester_zendesk_user_id,
                is_public=True,
                called_by=called_by,
                reimbursement_wallet_user=reimbursement_wallet_user,
            )
            log.info(
                "Added reimbursement request public comment to wallet zendesk ticket",
                ticket_id=str(ticket.id),
                user_id=str(reimbursement_wallet_user.user_id),
                reimbursement_request_id=str(reimbursement_request.id),
                wallet_id=str(reimbursement_wallet_user.reimbursement_wallet_id),
            )

            # get the comment id from the ticket_audit response
            comment_id = parse_comment_id_from_ticket_audit(
                ticket_audit=ticket_audit_response,
                user_id=reimbursement_wallet_user.member.id,
            )

            # get the comment body from the ticket_audit response
            comment_body = parse_ticket_comment_body_from_ticket_audit(
                ticket_audit=ticket_audit_response,
                user_id=reimbursement_wallet_user.member.id,
            )

            if enable_creating_reimbursement_message_to_db():
                rwu_channel = get_or_create_rwu_channel(reimbursement_wallet_user)
                try:
                    # get channel messages and append a new message that is associated with the public zendesk comment
                    add_reimbursement_request_to_wallet_channel(
                        rwu_channel=rwu_channel,
                        user=reimbursement_wallet_user.member,
                        message=comment_body if comment_body else None,
                        zendesk_comment_id=comment_id if comment_id else None,
                    )
                except Exception as e:
                    log.exception(
                        "Could not add public reimbursement request comment to member's wallet channel",
                        user_id=reimbursement_wallet_user.user_id,
                        channel_id=rwu_channel.id,
                        error=e,
                    )
        else:
            raise Exception(
                "Failed to comment on reimbursement request due to missing existing wallet ticket"
            )

    except Exception as e:
        log.error(
            "Failed to create comment in zendesk ticket for reimbursement request",
            ticket_id=str(reimbursement_wallet_user.zendesk_ticket_id),
            user_id=str(reimbursement_wallet_user.user_id),
            wallet_id=str(reimbursement_wallet_user.reimbursement_wallet_id),
            reason=format_exc(),
        )
        raise e


def _generate_zendesk_ticket(
    reimbursement_wallet_user: ReimbursementWalletUsers,
    ticket_subject: str,
    content: str,
    tags: list[str],
    status: str,
    user_need_when_solving_ticket: str = "",
    called_by: str | None = None,
    via_followup_source_id: int | None = None,
) -> int:
    log.info(
        "Creating Zendesk ticket for RWU",
        user_id=str(reimbursement_wallet_user.user_id),
    )
    zendesk_ticket_id = send_general_ticket_to_zendesk(
        user=reimbursement_wallet_user.member,
        ticket_subject=ticket_subject,
        content=content,
        tags=tags,
        status=status,
        called_by=called_by,
        via_followup_source_id=via_followup_source_id,
        user_need_when_solving_ticket=user_need_when_solving_ticket,
    )

    # We still need to assign the zendesk_ticket_id to the wallet
    # for the /v1/channels endpoint.
    reimbursement_wallet_user.zendesk_ticket_id = zendesk_ticket_id
    db.session.add(reimbursement_wallet_user)
    db.session.commit()
    return zendesk_ticket_id


def add_comment_to_ticket(
    ticket: Ticket,
    comment_body: str,
    author_id: int,
    is_public: bool,
    called_by: str,
    reimbursement_wallet_user: ReimbursementWalletUsers,
) -> TicketAudit:
    user_id = reimbursement_wallet_user.user_id
    log.info(
        "Adding comment to ticket",
        ticket_id=str(ticket.id),
        user_id=str(user_id),
        tags=ticket.tags,
    )
    ticket.status = "open"
    if ticket.tags is None:
        ticket.tags = []
    tags = set(ticket.tags)
    organization_tag = get_organization_tag(reimbursement_wallet_user)
    if organization_tag:
        tags.add(organization_tag)
    ticket.tags = list(tags)
    ticket.comment = Comment(body=comment_body, author_id=author_id, public=is_public)
    # update ticket comment
    updated_ticket = zenpy_client.update_ticket(ticket, user_id, called_by)
    return updated_ticket


def add_reimbursement_request_to_wallet_channel(
    rwu_channel: Channel,
    user: User,
    message: str | None,
    zendesk_comment_id: int | None,
) -> None:
    """
    Write member's reimbursement request message to the db
    :param rwu_channel:
    :param user:
    :param message:
    :param zendesk_comment_id:
    :return:
    """
    message = Message(
        user=user,
        channel=rwu_channel,
        body=message,
        zendesk_comment_id=zendesk_comment_id,
    )
    db.session.add(message)
    db.session.commit()
    log.info(
        "Added public reimbursement request comment to member's wallet channel",
        message_id=message.id,
        channel_id=rwu_channel.id,
        member_id=user.id,
        zendesk_comment_id=zendesk_comment_id,
    )


def get_organization_tag(reimbursement_wallet_user: ReimbursementWalletUsers) -> str:
    organization: Organization = (
        reimbursement_wallet_user.wallet.reimbursement_organization_settings.organization
    )
    return organization.name.lower().replace("-", "_").replace(" ", "_")
