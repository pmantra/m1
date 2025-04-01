from __future__ import annotations

import datetime

import ddtrace

from appointments.models.payments import Credit
from appointments.tasks.appointments import log
from authn.models.user import User
from common import stats
from eligibility import EnterpriseVerificationService, get_verification_service
from storage.connection import db
from tasks.queues import job
from tracks import service as tracks_svc

REFILL_CREDITS = 2000


@ddtrace.tracer.wrap()
@job("priority", traced_parameters=("appointment_id", "message_id"))
def refill_credits_for_enterprise_member(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    member_id: int,
    appointment_id: int | None = None,
    message_id: int | None = None,
) -> None:
    """
    If the user is an enterprise member and their active credits is below 1000,
    refill 2000 credits for that user.

    This is a workaround to prevent enterprise members from running out of credits.
    Ideally we should not check payments and credits for enterprise users at all.
    However, based on the current structure and how credit is used throughout the
    appointment and messaging flow, it is very difficult to decouple credits in the appointment
    and messaging lifecycles regardless of member types.
    """
    metric_name = "api.appointments.tasks.credits.refill_credits_for_enterprise_member"

    track_svc = tracks_svc.TrackSelectionService()
    is_enterprise_member = track_svc.is_enterprise(user_id=member_id)
    available_amount = Credit.available_amount_for_user_id(user_id=member_id)
    log.info(
        "Checking if the user is eligible for refilling the credits",
        user_id=member_id,
        appointment_id=appointment_id,
        message_id=message_id,
    )

    if not (is_enterprise_member and available_amount < 1000):
        log.info(
            "User is not eligible for a credit refill",
            user_id=member_id,
            appointment_id=appointment_id,
            message_id=message_id,
            is_enterprise_member=is_enterprise_member,
            available_credit_amount=available_amount,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:false", "variant:user_not_eligible"],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )
        return

    log.info(
        "Enterprise user has less than 1000 credits, refilling",
        user_id=member_id,
    )
    try:
        member = db.session.query(User).filter(User.id == member_id).one_or_none()
        if not member:
            log.error(
                "User not found while trying to refill credits",
                user_id=member_id,
                appointment_id=appointment_id,
                message_id=message_id,
            )
            stats.increment(
                metric_name=metric_name,
                tags=["success:false", "variant:error_user_not_found"],
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )
            return
        member_track = member.active_tracks[0]
        track_scheduled_end = member_track.get_scheduled_end_date()
        # Credit's expiration time should be the same as member track's end time
        # so that user can no longer use these credits when they are no longer a
        # enterprise member.
        # activated_at will be a minute ago so that `available_for_user_id` can pick up this Credit,
        # as it searches for credits created before now.replace(microsecond=0)
        verification_svc: EnterpriseVerificationService = get_verification_service()
        verification = verification_svc.get_verification_for_user_and_org(
            user_id=member_id,
            organization_id=member_track.client_track.organization.id,
        )
        credit = Credit(
            user_id=member_id,
            amount=REFILL_CREDITS,
            activated_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=1),
            expires_at=datetime.datetime.combine(
                track_scheduled_end, datetime.time(hour=23, minute=59, second=59)
            ),
            eligibility_member_id=verification.eligibility_member_id
            if verification
            else None,
            eligibility_verification_id=verification.verification_id
            if verification
            else None,
            eligibility_member_2_id=verification.eligibility_member_2_id
            if verification
            else None,
            eligibility_verification_2_id=verification.verification_2_id
            if verification
            else None,
            eligibility_member_2_version=verification.eligibility_member_2_version
            if verification
            else None,
        )
        db.session.add(credit)
        db.session.commit()
        log.info(
            f"Refilled {REFILL_CREDITS} credits to the enterprise user",
            user_id=member_id,
            appointment_id=appointment_id,
            message_id=message_id,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:true", "variant:success"],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )

    except Exception as e:
        log.error(
            "Error refilling credits for enterprise member",
            error=e.__class__.__name__,
            exception=e,
            appointment_id=appointment_id,
            message_id=message_id,
            user_id=member_id,
            available_credit_amount=available_amount,
        )
        stats.increment(
            metric_name=metric_name,
            tags=["success:false", "variant:error_exception_caught"],
            pod_name=stats.PodNames.CARE_DISCOVERY,
        )
