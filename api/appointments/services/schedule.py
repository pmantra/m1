from __future__ import annotations

import datetime
from contextlib import contextmanager
from typing import Iterator

import ddtrace
import sqlalchemy.orm
from flask_restful import abort
from redset.exceptions import LockTimeout
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.constants import ScheduleStates
from appointments.models.schedule_event import ScheduleEvent
from appointments.utils.booking import AvailabilityCalculator, AvailabilityTools
from authn.models.user import User
from common.models.scheduled_maintenance import ScheduledMaintenance
from models.actions import audit
from models.products import Product
from models.profiles import PractitionerProfile
from storage.connection import db
from tasks.forum import invalidate_posts_cache_for_user
from utils.cache import RedisLock
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


def validate_member_schedule(member_id: int) -> User:
    try:
        member = db.session.query(User).filter(User.id == member_id).one()
    except NoResultFound:
        abort(404, message="Invalid member ID")

    member_schedule_id = member.schedule.id if member.schedule else None

    if not member_schedule_id:
        abort(404, message="That user has no schedule!")

    return member


def update_practitioner_profile_next_availability_with_practitioner_id(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    session: sqlalchemy.orm.Session, practitioner_user_id: int, appointment_id: int
):
    profile = (
        session.query(PractitionerProfile)
        .filter(PractitionerProfile.user_id == practitioner_user_id)
        .first()
    )
    if profile:
        update_practitioner_profile_next_availability(profile=profile)
    else:
        log.error(
            "Cannot find the practitioner profile to update the next availability",
            practitioner_user_id=practitioner_user_id,
            appointment_id=appointment_id,
        )


@ddtrace.tracer.wrap()
def update_practitioner_profile_next_availability(
    profile: PractitionerProfile, skip_commit: bool = False
) -> None:
    user_id = profile.user.id
    log.info(
        "Running update_practitioner_profile_next_availability for practitioner profile",
        user_id=user_id,
    )

    # TODO: use get_product_for_practitioner for this logic, or assume product in
    #  AvailabilityCalculator
    # This is similar logic to get_product_for_practitioner, but here we do
    #  want to consider products that have is_promotional = True, despite not having
    #  a specific member in mind
    products = [
        p for p in profile.user.products if p.is_active and p.minutes is not None
    ]
    if products:
        product = min(products, key=lambda p: p.minutes)
    else:
        log.warning("User has no products - skipping.", user_id=user_id)
        return

    start = AvailabilityTools.pad_and_round_availability_start_time(
        datetime.datetime.utcnow(), profile.booking_buffer, profile.rounding_minutes
    )

    search_window = 365
    end = start + datetime.timedelta(days=search_window)
    profile = product.practitioner.practitioner_profile
    calculator = AvailabilityCalculator(practitioner_profile=profile, product=product)
    availability = calculator.get_availability(start_time=start, end_time=end, limit=1)

    old_next_availability = profile.next_availability
    if availability:
        first_availability = availability[0].scheduled_start
        if first_availability:
            profile.next_availability = first_availability
            log.info(
                "next_availability updated for user",
                user_id=user_id,
                new_next_availability=first_availability,
                old_next_availability=old_next_availability,
                start_time=start,
                end_time=end,
            )
        else:
            log.warning(
                "Empty scheduled_start date for practitioner",
                user_id=user_id,
                next_availability=old_next_availability,
                start_time=start,
                end_time=end,
            )
    else:
        log.info(
            "No availability found for practitioner",
            user_id=user_id,
            next_availability=profile.next_availability,
            start=start,
            end=end,
        )
        profile.next_availability = None

    try:
        db.session.add(profile)
        if skip_commit:
            db.session.flush()
        else:
            db.session.commit()
    except KeyError as e:
        log.error(
            "Attempted to add invalid practitioner profile",
            user_id=user_id,
            profile=profile,
            exception=e,
        )
    except Exception as e:
        log.error(
            "Exception updating practitioner profile",
            user_id=user_id,
            next_availability=profile.next_availability,
            exception=e,
        )

    invalidate_posts_cache_for_user.delay(
        user_id,
        service_ns="community_forum",
        team_ns=service_ns_team_mapper.get("community_forum"),
    )


def detect_schedule_conflict(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    schedule, starts_at, ends_at, existing_event_id=None, request=None
):
    log.info(f"Detecting conflicts for ({schedule}) {starts_at} - {ends_at}")
    existing = schedule.existing_events(starts_at, ends_at).filter(
        ScheduleEvent.state == ScheduleStates.available
    )

    if existing_event_id:
        existing = existing.filter(ScheduleEvent.id != existing_event_id)

    if existing.count() == 1:
        existing = existing.first()
        if not (existing.starts_at == ends_at or existing.ends_at == starts_at):
            audit(
                "schedule_events_conflict",
                request_args=request.json if request and request.is_json else None,
            )
            log.error(f"Conflicts with {existing}")
            abort(400, message="Conflict with existing availability!")

    elif existing.count() == 2:
        existing = sorted(existing.all(), key=lambda x: x.starts_at)
        if not (existing[0].ends_at == starts_at and existing[1].starts_at == ends_at):
            audit(
                "schedule_events_conflict",
                request_args=request.json if request and request.is_json else None,
            )
            log.error(f"Conflicts with {existing}")
            abort(400, message="Conflict with existing availability!")

    elif existing.count():
        audit(
            "schedule_events_conflict",
            request_args=request.json if request and request.is_json else None,
        )
        log.error(f"Conflicts with multiple: {existing.all()}")
        abort(400, message="Conflict with existing availability!")

    overlapped_maintenance = get_overlapping_maintenance_windows(starts_at, ends_at)

    if overlapped_maintenance:
        abort(400, message="Conflict with existing maintenance window!")


def get_overlapping_maintenance_windows(
    starts_at: datetime.datetime, ends_at: datetime.datetime
) -> sqlalchemy.engine.ResultProxy:
    # finding potential overlaps with maintenance http://stackoverflow.com/a/325964/
    return (
        db.session.query(ScheduledMaintenance)
        .filter(
            (ScheduledMaintenance.scheduled_start <= ends_at)
            & (starts_at <= ScheduledMaintenance.scheduled_end)
        )
        .all()
    )


def _get_booking_lock_key(provider_id: int, scheduled_start_date: datetime.date) -> str:
    if not provider_id or not scheduled_start_date:
        log.error(
            "Missing provider_id or scheduled_start_date during booking",
            provider_id=provider_id,
            scheduled_start_date=scheduled_start_date,
        )
        raise RuntimeError("Missing provider_id or scheduled_start_date during booking")

    return f"appointment_booking_{provider_id}_{scheduled_start_date.isoformat()}"


class BookingConflictException(Exception):
    pass


@contextmanager
def managed_appointment_booking_availability(
    product: Product, scheduled_start: datetime.datetime, member: User
) -> Iterator:
    """
    A context manager for safely booking appointment slots and preventing race conditions.
    A read/write lock is acquired and released around the context block.
    Raises a BookingConflictException if the slot is unavailable or if the lock is in use.
    This should be rare and may be retryable. Most callers should check for availability first
    before entering this locked region, so this is a double-check for avoiding races.

    Example use:
    ```
    try:
        with managed_appointment_availability(...):
           appt = Appointment.create(...)
           db.session.add(appt)
           db.session.commit()
    except BookingConflictException e:
        ....
    ```
    """
    if (
        not product
        or not product.user_id
        or not product.practitioner
        or not product.practitioner.practitioner_profile
    ):
        log.error(
            "Product with misconfigured practitioner",
            product_id=product.id if product else None,
        )
        raise RuntimeError(f"Product with misconfigured practitioner {product}")

    try:
        with RedisLock(
            _get_booking_lock_key(product.user_id, scheduled_start.date()),
            timeout=1,
            expires=2,
        ):
            calculator = AvailabilityCalculator(
                practitioner_profile=product.practitioner.practitioner_profile,
                product=product,
            )
            scheduled_end = scheduled_start + datetime.timedelta(
                minutes=product.minutes  # type: ignore[arg-type]
            )
            availability = calculator.get_availability(
                start_time=scheduled_start, end_time=scheduled_end, member=member
            )
            is_available = availability and (
                availability[0].scheduled_start == scheduled_start
            )
            if not is_available:
                log.warning(
                    "Timeslot unavailable during attempted booking",
                    product_id=product.id,
                    practitioner_id=product.user_id,
                    member_id=member.id,
                    scheduled_start=scheduled_start,
                )
                raise BookingConflictException("Timeslot unavailable")
            yield

    except LockTimeout:
        log.warning(
            "Lock unavailable during attempted booking",
            product_id=product.id,
            practitioner_id=product.user_id,
            member_id=member.id,
            scheduled_start=scheduled_start,
        )
        raise BookingConflictException("Lock unavailable")
