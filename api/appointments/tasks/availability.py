from __future__ import annotations

import datetime
from typing import Any, List

from redset.exceptions import LockTimeout
from sqlalchemy import or_, true

from appointments.models.appointment import Appointment
from appointments.models.schedule import Schedule
from appointments.models.schedule_event import ScheduleEvent
from appointments.resources.practitioners_availabilities import (
    _get_practitioner_contract_priorities,
)
from appointments.services.recurring_schedule import (
    RecurringScheduleAvailabilityService,
)
from appointments.services.schedule import update_practitioner_profile_next_availability
from appointments.utils.availability_notifications import (
    update_next_availability_and_alert_about_availability,
)
from appointments.utils.booking import MassAvailabilityCalculator
from authn.models.user import User
from common import stats
from common.stats import PodNames

# DO NOT REMOVE BELOW 2 LINES. SQLALCHEMY NEEDS IT FOR MAPPER INSTANTIATION
from messaging.models.messaging import MessageBilling  # noqa: F401
from models.actions import ACTIONS, audit
from models.products import Product
from models.profiles import PractitionerProfile
from models.referrals import ReferralCodeUse  # noqa: F401
from models.verticals_and_specialties import DOULA_ONLY_VERTICALS, Vertical
from payments.models.practitioner_contract import PractitionerContract
from providers.service.provider import ProviderService
from storage.connection import db
from tasks.queues import job
from utils.cache import RedisLock
from utils.log import logger

log = logger(__name__)


@job
def update_practitioners_next_availability(prac_ids=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not prac_ids:
        prac_ids = get_prac_ids_with_expired_next_availability()
    for prac_id in prac_ids:
        log.info("Update Practitioner Next Availability", user_id=prac_id)
        update_practitioner_next_availability_job.delay(
            prac_id, team_ns="care_discovery"
        )


@job(traced_parameters=("practitioner_id",))
def update_practitioner_next_availability_job(practitioner_id: int) -> None:
    log.info("Update Practitioner Next Availability Job", user_id=practitioner_id)
    profile = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id == practitioner_id)
        .first()
    )

    if profile:
        try:
            with RedisLock(
                f"update_practitioners_cache_{practitioner_id}",
                timeout=10,
                expires=20,
            ):
                update_practitioner_profile_next_availability(profile)
        except LockTimeout:
            log.warning(
                f"Could not lock on update_practitioners_cache_{practitioner_id}, returning"
            )
        except Exception as e:
            log.error(
                "Unknown error with update_practitioner_next_availability_job",
                user_id=practitioner_id,
                exception=e,
            )

    else:
        log.warning("Bad practitioner_id: %s", practitioner_id)


@job
def update_staff_practitioners_percent_booked(recent_days: int = 30) -> None:
    profiles = (
        db.session.query(PractitionerProfile)
        .join(
            PractitionerContract,
            PractitionerProfile.user_id == PractitionerContract.practitioner_id,
        )
        .filter(PractitionerContract.active.is_(True))  # type: ignore[attr-defined] # overloaded function has no attribute "is_"
        .filter(PractitionerContract.emits_fees.is_(False))
        .all()
    )

    log.info("Got pracs to update their percent_booked.", n_profiles=len(profiles))
    for profile in profiles:
        profile.percent_booked = percent_booked_for_profile(profile, recent_days)
        db.session.add(profile)

    db.session.commit()
    log.info("All set updating % booked!")


def percent_booked_for_profile(profile, recent_days=30):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    now = datetime.datetime.utcnow()
    bottom_anchor = now - datetime.timedelta(days=recent_days)

    all_bookings = (
        db.session.query(Appointment)
        .filter(
            Appointment.product_id.in_([p.id for p in profile.user.products]),
            Appointment.scheduled_start >= bottom_anchor,
            Appointment.scheduled_end <= now,
        )
        .all()
    )

    total_bookings = 0
    for booking in all_bookings:
        total_bookings = total_bookings + booking.product.minutes

    total_avail = None
    if profile.user.schedule:
        total_avail = profile.user.schedule.availability_minutes_in_window(
            bottom_anchor, now
        )

    if not total_avail:
        log.info("No availability for %s, return 0", profile)
        return 0

    percent_booked = total_bookings / total_avail
    log.info(
        "Got %s (raw) for percent booked for %s: (%s/%s)",
        percent_booked,
        profile,
        total_bookings,
        total_avail,
    )
    final_percent = int(percent_booked * 100)
    return final_percent


def get_prac_ids_with_expired_next_availability():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    A practitioner has expired next_availability if one of the two following conditions are met:
    a) They are active and their next_availability is 'old', aka, before now+buffer
    b) They are active, their next_availability is None, and they have schedule_events in the future
    """
    booking_buffers = (
        db.session.query(PractitionerProfile.booking_buffer).distinct().all()
    )
    booking_buffers = sorted([r[0] for r in booking_buffers], reverse=True)
    distinct_practice_ids = set()
    for _buffer in booking_buffers:
        expired_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=_buffer)

        now = datetime.datetime.now()
        end_time = now + datetime.timedelta(days=365)

        _expired = (
            db.session.query(PractitionerProfile.user_id)
            .join(User, User.id == PractitionerProfile.user_id)
            .join(Product, Product.user_id == PractitionerProfile.user_id)
            .join(
                Schedule,
                Schedule.user_id == PractitionerProfile.user_id,
            )
            .join(
                ScheduleEvent,
                ScheduleEvent.schedule_id == Schedule.id,
            )
            .filter(
                PractitionerProfile.booking_buffer == _buffer,
                User.active == True,
                Product.is_active == True,
                ScheduleEvent.ends_at >= now,
                ScheduleEvent.starts_at <= end_time,
                or_(
                    PractitionerProfile.next_availability == None,
                    PractitionerProfile.next_availability < expired_time,
                ),
            )
            .distinct()
            .all()
        )

        log.info(
            "Got chunk practitioners with expired next availability",
            n_practitioners=len(_expired),
            expired_time=expired_time,
            buffer=_buffer,
        )
        distinct_practice_ids.update(id for (id,) in _expired)

    prac_ids = list(distinct_practice_ids)
    log.info(
        "Got practitioners with expired next availability",
        n_practitioners=len(prac_ids),
        prac_ids=prac_ids,
    )
    return prac_ids


@job(team_ns="mpractice_core", service_ns="provider_availability")
def create_recurring_availability(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    starts_at: datetime.datetime,
    ends_at: datetime.datetime,
    frequency: str,
    until: datetime.datetime,
    week_days_index: list[int],
    member_timezone: str,
    user_id: int,
):
    user = db.session.query(User).get(user_id)
    schedule_id = user.schedule.id
    recurring_schedule_service = RecurringScheduleAvailabilityService()
    try:
        recurring_schedule_service.create_schedule_recurring_block(
            starts_at=starts_at,
            ends_at=ends_at,
            frequency=frequency,
            until=until,
            schedule_id=schedule_id,
            week_days_index=week_days_index,
            member_timezone=member_timezone,
            user_id=user_id,
        )
    except Exception as e:
        log.error(
            "Error creating schedule recurring block and schedule events",
            user_id=user_id,
            schedule_id=schedule_id,
            starts_at=starts_at,
            until=until,
            error=str(e),
        )
        stats.increment(
            metric_name="appointments.tasks.availability.create_recurring_availability",
            pod_name=PodNames.MPRACTICE_CORE,
            tags=["error:true", f"error_cause:{e}"],
        )
        raise e
    log.info("Creating recurring availability", schedule_id=schedule_id)
    practitioner_profile = user.practitioner_profile

    update_next_availability_and_alert_about_availability(
        practitioner_profile=practitioner_profile,
        user_full_name=user.full_name,
        starts_at=starts_at,
        ends_at=ends_at,
        until=until,
        recurring=True,
    )


@job(team_ns="mpractice_core", service_ns="provider_availability")
def delete_recurring_availability(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_id: int,
    schedule_recurring_block_id: int,
):
    user = db.session.query(User).get(user_id)
    recurring_schedule_service = RecurringScheduleAvailabilityService()
    schedule_recurring_block = (
        recurring_schedule_service.get_schedule_recurring_block_by_id(
            schedule_recurring_block_id=schedule_recurring_block_id,
        )
    )

    if schedule_recurring_block:
        try:
            recurring_schedule_service.delete_schedule_recurring_block(
                schedule_recurring_block_id=schedule_recurring_block_id,
                user_id=user_id,
            )
        except Exception as e:
            log.error(
                "Error deleting schedule recurring block",
                schedule_recurring_block_id=schedule_recurring_block_id,
                error=str(e),
            )
            stats.increment(
                metric_name="appointments.tasks.availability.delete_recurring_availability",
                pod_name=PodNames.MPRACTICE_CORE,
                tags=["error:true", f"error_cause:{e}"],
            )
            raise e
        log.info(
            "Deleting recurring availability",
            schedule_recurring_block_id=schedule_recurring_block_id,
        )

        audit(
            ACTIONS.availability_removed,
            user.id,
            availability_type="recurring",
            block_start=str(schedule_recurring_block.starts_at),
            block_until=str(schedule_recurring_block.until),
        )
        update_practitioner_profile_next_availability(user.practitioner_profile)
    else:
        log.error(
            "Error, no scheduled_recurring_block found",
            schedule_recurring_block_id=schedule_recurring_block_id,
        )
        stats.increment(
            metric_name="appointments.tasks.availability.delete_recurring_availability",
            pod_name=PodNames.MPRACTICE_CORE,
            tags=["error:true", "error_cause:schedule_recurring_block_not_found"],
        )


@job()
def report_doula_availability() -> None:
    log.info("Starting to check future doula availability")
    future_time = datetime.datetime.utcnow() + datetime.timedelta(days=28)
    # get list of providers
    verticals = set(DOULA_ONLY_VERTICALS)
    verticals.remove("care advocate")
    profiles: list[PractitionerProfile] = (
        db.session.query(PractitionerProfile)
        .filter(PractitionerProfile.active == true())
        .join(PractitionerProfile.verticals)
        .filter(Vertical.name.in_(verticals))
        .all()
    )
    log.info("Checking future doula availability", num_doulas_checked=len(profiles))

    available_doulas = [
        profile
        for profile in profiles
        if profile.next_availability and profile.next_availability <= future_time
    ]

    stats.gauge(
        metric_name="appointments.tasks.availability.report_doula_availability",
        metric_value=len(available_doulas),
        pod_name=stats.PodNames.CARE_DISCOVERY,
    )
    log.info(
        "Computed doula availability.",
        num_doulas_checked=len(profiles),
        num_doulas_available=len(available_doulas),
    )
    return


@job
def log_practitioner_future_days_availability(
    user_id: int,
    practitioner_ids: List[int],
    can_prescribe: bool,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    vertical_name: str,
    provider_steerage_sort: Any | None,
) -> None:
    user = db.session.query(User).get(user_id)
    num_days = (end_time - start_time).days

    log.info(
        "Start to build practitioner availability",
        user_id=user.id,
        start_time=start_time,
        end_time=end_time,
        provider_steerage_sort=provider_steerage_sort,
        practitioner_ids=practitioner_ids,
        can_prescribe=can_prescribe,
    )

    practitioner_profiles = ProviderService().list_available_practitioners_query(
        user, practitioner_ids, can_prescribe, provider_steerage_sort
    )

    contract_priority_by_practitioner_id = None
    if provider_steerage_sort:
        contract_priority_by_practitioner_id = _get_practitioner_contract_priorities(
            practitioner_profiles
        )

    availabilities = MassAvailabilityCalculator().get_practitioner_availabilities(
        practitioner_profiles=practitioner_profiles,
        start_time=start_time,
        end_time=end_time,
        member=user,
        limit=100 * num_days,
        offset=0,
        vertical_name=vertical_name,
        contract_priority_by_practitioner_id=contract_priority_by_practitioner_id,
    )

    data = [
        {
            "p_id": a.practitioner_id,
            "duration": a.duration,
            "prod_id": a.product_id,
            "prod_price": a.product_price,
            "credits": a.availabilities[0].total_available_credits
            if len(a.availabilities)
            else 0,
            "slots": [
                {
                    "s": avail.scheduled_start.strftime("%Y%m%d%H%M"),
                    "e": avail.scheduled_end.strftime("%Y%m%d%H%M"),
                    "p_id": a.practitioner_id,
                }
                for avail in a.availabilities
            ],
        }
        for a in availabilities
    ]

    log.info(
        "Practitioner availability result",
        n_practitioners=len(practitioner_profiles),
        start_time=start_time,
        end_time=end_time,
        vertical_name=vertical_name,
        user_id=user.id,
        availabilities=data,
    )
