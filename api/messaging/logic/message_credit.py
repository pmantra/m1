from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, List, Tuple

import ddtrace

from appointments.models.payments import Credit
from appointments.tasks.credits import refill_credits_for_enterprise_member
from authn.models.user import User
from messaging.models.messaging import Channel, Message, MessageBilling, MessageCredit
from messaging.utils.common import wallet_exists_for_channel
from models.enterprise import Organization
from storage.connection import db
from tracks import service as tracks_svc
from utils.log import logger

log = logger(__name__)


class MessageCreditException(Exception):
    def __init__(self, user_is_enterprise: bool):
        self.user_is_enterprise = user_is_enterprise


@ddtrace.tracer.wrap()
def pay_with_credits(
    amount: int, available_credits: Iterable[Credit]
) -> Tuple[int, List[MessageCredit]]:
    """
    Pay for messaging product purchase with Maven Credit.
    Returns a tuple of remaining unpaid balance and a list of maven credit used.
    """
    balance = amount
    used_credits = []

    if not available_credits:
        log.debug("No Maven Credits.")
        return balance, used_credits

    total_credit_amount = sum(c.amount for c in available_credits)
    now = datetime.utcnow()

    if balance > total_credit_amount:
        balance -= total_credit_amount

        for a_credit in available_credits:
            a_credit.used_at = now
            used_credits.append(a_credit)
        log.debug(
            f"Not enough credit to cover {amount}. Apply all available credits {total_credit_amount}"
        )
        db.session.add_all(available_credits)
        db.session.commit()
    else:
        # sort credits to be applied, oldest first
        available_credits = sorted(
            available_credits,
            key=lambda x: x.expires_at if x.expires_at else x.created_at,
        )
        # apply each applicable credit atomically
        for a_credit in available_credits:
            if balance - a_credit.amount <= 0:
                a_credit.used_at = now
                used_credits.append(a_credit)

                excess = a_credit.amount - balance
                if excess > 0:
                    new_credit = a_credit.copy_with_excess(excess)
                    db.session.add(new_credit)
                    used_credits.append(a_credit)
                    log.debug(
                        f"Partial credit excess: {excess} carried over to {new_credit}"
                    )
                db.session.add(a_credit)
                db.session.commit()
                log.debug(f"Last credit to be applied {a_credit}")
                balance = 0  # paid in full
                break  # important to stop right here!
            else:
                a_credit.used_at = now
                used_credits.append(a_credit)
                db.session.add(a_credit)
                db.session.commit()
                balance = int(balance - a_credit.amount)
                log.debug(f"Applied fully: {a_credit}")

    log.debug(f"Remaining balance owed {balance}")
    return balance, used_credits


@ddtrace.tracer.wrap()
def _create_reply_message(message: Message, respond_by: datetime, user: User) -> None:
    """
    Reply messages are messages in the channel after the first message.
    """
    track_svc = tracks_svc.TrackSelectionService()
    org_id = track_svc.get_organization_id_for_user(user_id=user.id)
    has_active_tracks = bool(track_svc.member_tracks.get_active_tracks(user_id=user.id))

    available_credit = Credit.available_amount_for_user(user)
    msg_credit: MessageCredit | None = None
    if org_id and has_active_tracks:
        # enterprise user
        organization = db.session.query(Organization).get(org_id)
        org_msg_price = organization.message_price
        if available_credit < org_msg_price:
            log.warn(
                "User does not have enough enterprise credit to buy a message, refilling now.",
                user_id=user.id,
                balance=available_credit,
            )
            refill_credits_for_enterprise_member(
                member_id=user.id,
                message_id=message.id,
            )
            # if the job somehow didn't refill, fail to send
            # else continue with refilled credits
            available_credit = Credit.available_amount_for_user(user)
            if available_credit < org_msg_price:
                db.session.rollback()
                raise MessageCreditException(user_is_enterprise=True)

        available_credits = Credit.available_for_user(user).all()
        pay_with_credits(organization.message_price, available_credits)

        purchase = MessageBilling.create(user_id=user.id, json={"enterprise": True})

        msg_credit = MessageCredit.create(
            count=1, user_id=user.id, message_billing_id=purchase.id
        )[0]
        # check to see if they'll be out of credits next time they try to message, if so refill
        new_available_credit = Credit.available_amount_for_user(user)
        if new_available_credit < org_msg_price:
            log.info(
                "refilling credits for enterprise member.",
                user_id=user.id,
                balance=new_available_credit,
            )
            refill_credits_for_enterprise_member.delay(
                member_id=user.id, message_id=message.id, team_ns="virtual_care"
            )
    else:
        # regular consumer, apply oldest maven credit first
        log.info(
            "evaluating credits for non-enterprise member.",
            user_id=user.id,
            org_id=org_id,
            has_active_tracks=has_active_tracks,
        )
        msg_credit = MessageCredit.first_unused_credit_for_user(user)

    if not msg_credit:
        log.warn(
            "member does not have enough credit to message.",
            user_id=user.id,
            org_id=org_id,
            has_active_tracks=has_active_tracks,
        )
        raise MessageCreditException(user_is_enterprise=False)

    # redeem message credit
    msg_credit.message = message
    msg_credit.respond_by = respond_by
    db.session.add(msg_credit)


def _create_free_message(message, respond_by):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.flush()  # get id but not committed
    MessageCredit.create(
        count=1,
        user_id=message.user_id,
        message_id=message.id,
        respond_by=respond_by,
        json={"free": True},
    )


@ddtrace.tracer.wrap()
def verify_channel_billing_details(
    channel: Channel,
    message: Message,
    user: User,
) -> None:
    default_response_time_hours = 24
    practitioner_response_time_hours: int | None = None

    if not wallet_exists_for_channel(channel.id):
        if (
            channel.practitioner is None
            or channel.practitioner.practitioner_profile is None
        ):
            raise AttributeError(
                "practitioner or practitioner_profile or not available on channel"
            )
        practitioner_response_time_hours = (
            channel.practitioner.practitioner_profile.response_time
        )

    message_respond_by_hours = (
        practitioner_response_time_hours or default_response_time_hours
    )
    respond_by = datetime.utcnow() + timedelta(hours=message_respond_by_hours)

    if channel.internal:
        # messages in internal channel are free and add a message credit
        # for the free message to facilitate alerts to respond
        _create_free_message(message, respond_by)
    else:
        # check credit first
        _create_reply_message(message, respond_by, user)


@ddtrace.tracer.wrap()
def allocate_message_credits(channel: Channel, message: Message, user: User) -> None:
    if user.is_practitioner:
        mark_all_message_credits_as_responded_to(channel, message)
    else:
        verify_channel_billing_details(channel, message, user)


@ddtrace.tracer.wrap()
def mark_all_message_credits_as_responded_to(
    channel: Channel, message: Message
) -> None:
    """
    Associates all message credits in a channel with a response
    """
    now = datetime.utcnow()
    search_window = datetime.utcnow() - timedelta(weeks=4)
    all_unused_msg_credits = (
        db.session.query(MessageCredit.id)
        .join(MessageCredit.message)
        .join(Message.user)
        .filter(Message.channel_id == channel.id)
        .filter(User.is_member == True)  # noqa
        .filter(MessageCredit.responded_at.is_(None))
        .filter(MessageCredit.response_id.is_(None))
        .filter(Message.created_at >= search_window)
        .all()
    )

    all_unused_msg_credit_ids = [mc[0] for mc in all_unused_msg_credits]

    db.session.query(MessageCredit).filter(
        MessageCredit.id.in_(all_unused_msg_credit_ids)
    ).update(
        {"responded_at": now, "response_id": message.id}, synchronize_session="fetch"
    )
