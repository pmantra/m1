from __future__ import annotations

import json
from datetime import datetime

from appointments.models.constants import APPOINTMENT_STATES, PRIVACY_CHOICES
from mpractice.error import InvalidPrivacyError


def validate_privacy(privacy: str | None) -> str | None:
    allowed = [
        PRIVACY_CHOICES.anonymous,
        PRIVACY_CHOICES.basic,
        PRIVACY_CHOICES.full_access,
    ]
    if privacy is None or (privacy and privacy.lower() in allowed):
        return privacy
    raise InvalidPrivacyError(f"{privacy} not an allowed privacy choice!")


def get_state(
    scheduled_start: datetime | None = None,
    scheduled_end: datetime | None = None,
    member_started_at: datetime | None = None,
    member_ended_at: datetime | None = None,
    practitioner_started_at: datetime | None = None,
    practitioner_ended_at: datetime | None = None,
    cancelled_at: datetime | None = None,
    disputed_at: datetime | None = None,
    payment_captured_at: datetime | None = None,
    payment_amount: float | None = None,
    credit_latest_used_at: datetime | None = None,
    total_used_credits: float | None = None,
    fees_count: int | None = None,
    appointment_json: str | None = None,
) -> str | None:
    """
    When updating the logic for state computation,
    make sure to update the corresponding logic in appointments/models/appointment.py
    """
    started_at = get_started_at(
        member_started_at=member_started_at,
        practitioner_started_at=practitioner_started_at,
    )
    ended_at = get_ended_at(
        member_started_at=member_started_at,
        member_ended_at=member_ended_at,
        practitioner_started_at=practitioner_started_at,
        practitioner_ended_at=practitioner_ended_at,
    )
    fee_paid_at = get_fee_paid_at(
        payment_captured_at=payment_captured_at,
        credit_latest_used_at=credit_latest_used_at,
    )
    fee_paid = get_fee_paid(
        appointment_json=appointment_json,
        payment_captured_at=payment_captured_at,
        payment_amount=payment_amount,
        total_used_credits=total_used_credits,
    )
    now = datetime.utcnow()

    if cancelled_at:
        return APPOINTMENT_STATES.cancelled
    elif disputed_at:
        return APPOINTMENT_STATES.disputed
    elif scheduled_start and started_at:
        if ended_at:
            if (fee_paid_at and fee_paid != 0) or (
                fees_count is not None and fees_count > 0
            ):
                return APPOINTMENT_STATES.payment_resolved
            else:
                return APPOINTMENT_STATES.payment_pending
        elif scheduled_end > now and not (member_ended_at or practitioner_ended_at):
            return APPOINTMENT_STATES.occurring
        elif scheduled_end and scheduled_end < now and not ended_at:
            return APPOINTMENT_STATES.overflowing
        elif member_ended_at or practitioner_ended_at:
            return APPOINTMENT_STATES.incomplete
    elif scheduled_start:
        if scheduled_start < now:
            return APPOINTMENT_STATES.overdue
        else:
            return APPOINTMENT_STATES.scheduled

    return None


def get_started_at(
    member_started_at: datetime | None, practitioner_started_at: datetime | None
) -> datetime | None:
    started_at = None
    if member_started_at and practitioner_started_at:
        started_at = max(member_started_at, practitioner_started_at)
    return started_at


def get_ended_at(
    member_started_at: datetime | None,
    member_ended_at: datetime | None,
    practitioner_started_at: datetime | None,
    practitioner_ended_at: datetime | None,
) -> datetime | None:
    started_at = get_started_at(member_started_at, practitioner_started_at)
    ended_at = None
    if started_at and member_ended_at and practitioner_ended_at:
        ended_at = min(member_ended_at, practitioner_ended_at)
    return ended_at


def get_fee_paid_at(
    payment_captured_at: datetime | None, credit_latest_used_at: datetime | None
) -> datetime | None:
    candidates = []
    if payment_captured_at:
        candidates.append(payment_captured_at)
    if credit_latest_used_at:
        candidates.append(credit_latest_used_at)
    return max(candidates) if candidates else None


def get_fee_paid(
    appointment_json: str | None,
    payment_captured_at: datetime | None,
    payment_amount: float | None,
    total_used_credits: float | None,
) -> float:
    fee_paid = 0.0
    if appointment_json:
        fee_paid += (
            json.loads(appointment_json).get("plan_cancellation_paid_amount", 0) or 0
        )
    if payment_captured_at and payment_amount:
        fee_paid += payment_amount
    if total_used_credits:
        fee_paid += total_used_credits
    return fee_paid


def get_full_name(first_name: str | None = None, last_name: str | None = None) -> str:
    if not first_name and not last_name:
        return ""
    full_name = []
    if first_name:
        full_name.append(first_name)
    if last_name:
        full_name.append(last_name)
    return " ".join(full_name)


def get_member_name(
    privacy: str | None, member_first_name: str | None, member_last_name: str | None
) -> str:
    if privacy == PRIVACY_CHOICES.anonymous:
        member_name = "Anonymous"
    else:
        member_name = get_full_name(member_first_name, member_last_name)
    return member_name
