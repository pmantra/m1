from __future__ import annotations

import datetime
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, List, Optional

import ddtrace
import pytz
from sqlalchemy import func, or_, text

from appointments.models.appointment import Appointment
from appointments.models.constants import ScheduleStates
from appointments.models.payments import Credit
from appointments.models.schedule import Schedule
from appointments.models.schedule_event import ScheduleEvent
from authn.models.user import User
from models.products import Product
from models.profiles import PractitionerProfile, practitioner_verticals
from models.verticals_and_specialties import Vertical
from storage.connection import db
from utils.log import logger

log = logger(__name__)

APPOINTMENT_SEARCH_BUFFER = datetime.timedelta(days=1)
MASS_AVAILABILITY_PREP_BUFFER = "mass_availability_prep_buffer"

DATE_STRING_FORMAT = "%Y-%m-%d"
DEFAULT_TIMEZONE = "US/Eastern"


@dataclass
class PotentialAppointment:
    __slots__ = ("scheduled_start", "scheduled_end", "total_available_credits")
    scheduled_start: datetime.datetime
    scheduled_end: datetime.datetime
    total_available_credits: int


@dataclass
class TimeRange:
    __slots__ = ("start_time", "end_time")
    start_time: datetime.datetime | None
    end_time: datetime.datetime | None

    def localize(self, tz):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.start_time:
            self.start_time = self.start_time.replace(tzinfo=tz)
        if self.end_time:
            self.end_time = self.end_time.replace(tzinfo=tz)


class AvailabilityTools:
    @staticmethod
    @ddtrace.tracer.wrap()
    def pad_and_round_availability_start_time(
        raw_start_time: datetime.datetime,
        booking_buffer: int,
        rounding_minutes: int,
    ) -> datetime.datetime:
        """
        Takes a raw time (often now, but not necessarily), adds a practitioner's
        booking_buffer, and rounds the time to the practitioner's rounding_minutes

        Used to get the start_time for a product availability search
        """
        min_time = datetime.datetime.utcnow().replace(
            microsecond=0
        ) + datetime.timedelta(minutes=booking_buffer)

        if raw_start_time < min_time:
            starts_at = min_time
        else:
            starts_at = raw_start_time

        # This is for nearest 10 minutes rounding
        starts_at += datetime.timedelta(minutes=9, seconds=59, microseconds=999999)
        starts_at = starts_at.replace(
            minute=starts_at.minute - (starts_at.minute % rounding_minutes),
            second=0,
            microsecond=0,
        )
        return starts_at

    @staticmethod
    @ddtrace.tracer.wrap()
    def get_lowest_price_products_for_practitioners(
        profiles: list[PractitionerProfile],
        vertical_name: str | None = None,
    ) -> dict | None:
        practitioner_ids = [p.user_id for p in profiles]
        # Create empty dict to return
        products_with_min_price_per_user_dict = {
            p_id: None for p_id in practitioner_ids
        }

        if vertical_name:
            products_with_min_price_per_user = (
                db.session.query(Product)
                .filter(
                    Product.is_active == True,
                    Product.minutes.isnot(None),
                    Product.user_id.in_(practitioner_ids),
                )
                .join(Vertical, Product.vertical_id == Vertical.id)
                .filter(Vertical.name == vertical_name)
            ).all()

        else:
            products_with_min_price_per_user = (
                db.session.query(Product).filter(
                    Product.is_active == True,
                    Product.minutes.isnot(None),
                    Product.user_id.in_(practitioner_ids),
                )
            ).all()

        Product.sort_products_by_price(products_with_min_price_per_user)
        for product in products_with_min_price_per_user:
            if products_with_min_price_per_user_dict[product.user_id] is None:
                products_with_min_price_per_user_dict[product.user_id] = product

        return products_with_min_price_per_user_dict

    @staticmethod
    @ddtrace.tracer.wrap()
    def get_product_for_practitioner(
        profile: PractitionerProfile, vertical_name: Optional[str] = None
    ) -> Optional[Product]:
        """See /v1/products for the logic this needs to mimic. Frontend uses the 1st product from that."""

        def _is_product_valid_and_in_vertical(p: Product) -> bool:
            is_valid = p.minutes is not None and p.is_active
            in_vertical = True
            if vertical_name:
                in_vertical = p.vertical and p.vertical.name == vertical_name
            return is_valid and in_vertical

        products = [
            p for p in profile.user.products if _is_product_valid_and_in_vertical(p)
        ]
        Product.sort_products_by_price(products)
        return products[0] if products else None

    @staticmethod
    @ddtrace.tracer.wrap()
    def has_had_ca_intro_appointment(member: Optional[User]) -> bool:
        # Need to check if an appointment with a CA exists for this member
        if not member:
            return False

        # TODO: At some point in life we would benefit from storing if an appt is an intro appt in the db. There is a 'purpose' column that we could use for that
        first_ca_appt = (
            db.session.query(Schedule.id)
            .filter(Schedule.user_id == member.id)
            .join(Appointment, Schedule.id == Appointment.member_schedule_id)
            .join(Product, Appointment.product_id == Product.id)
            .join(PractitionerProfile, Product.user_id == PractitionerProfile.user_id)
            .join(
                practitioner_verticals,
                PractitionerProfile.user_id == practitioner_verticals.c.user_id,
            )
            .join(
                Vertical,
                practitioner_verticals.c.vertical_id == Vertical.id,
            )
            .filter(Vertical.name == "Care Advocate")
            .first()
        )

        return first_ca_appt is not None


class AvailabilityCalculator:
    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, practitioner_profile, product, load_practitioner_user_entity=True
    ):
        from care_advocates.models.assignable_advocates import AssignableAdvocate

        self.practitioner_profile = practitioner_profile

        self.assignable_advocate = None
        if self.practitioner_profile.is_cx:
            self.assignable_advocate = AssignableAdvocate.query.filter(
                AssignableAdvocate.practitioner == self.practitioner_profile
            ).one_or_none()

        self.product = product
        if practitioner_profile.user_id != self.product.user_id:
            log.error(
                "Cannot calculate booking values for a product and practitioner mismatch.",
                practitioner_profile=practitioner_profile.user_id,
                product=product.id,
                product_user=product.user_id,
            )
            raise ValueError(
                "Cannot calculate booking values for a product and practitioner mismatch."
            )
        # Instantiating the self.practitioner variable is expensive and actually only used when calling AvailabilityCalculator.get_availabilty
        # Hence, we want to be able to disable loading it
        if load_practitioner_user_entity:
            self.practitioner = self.practitioner_profile.user

    @property
    def min_start_time(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        now = datetime.datetime.utcnow()
        buffer_length = datetime.timedelta(
            minutes=max(self.prep_time, self.practitioner_profile.booking_buffer)
        )
        return now + buffer_length

    @property
    def prep_time(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Time required between appointments for this product."""
        return (
            self.product.prep_buffer
            or self.practitioner_profile.default_prep_buffer
            or 0
        )

    # Appointment lengths in minutes will be bumped up to the nearest multiple of this value:
    _APPOINTMENT_STEP_LENGTH = 5.0

    @property
    def padded_length(self) -> int:
        """Approximate length of appointments for this product."""
        length = int(
            math.ceil(self.product.minutes / self._APPOINTMENT_STEP_LENGTH)
        ) * int(self._APPOINTMENT_STEP_LENGTH)
        return length

    @property
    def next_possible_booking_start(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """The hypothetical next possible appointment start time assuming no conflicts and full availability."""
        start = AvailabilityTools.pad_and_round_availability_start_time(
            datetime.datetime.utcnow(),
            self.practitioner_profile.booking_buffer,
            self.practitioner_profile.rounding_minutes,
        )
        return start

    @property
    def last_possible_booking(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """The last possible moment the user's stripe charge for an appointment can be captured."""
        return self.next_possible_booking_start + datetime.timedelta(days=7)

    @ddtrace.tracer.wrap()
    def get_availability(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        member: Optional[User] = None,
        limit: Optional[int] = None,
        check_daily_intro_capacity: Optional[bool] = True,
    ) -> List[PotentialAppointment]:
        """
        Get all possible appointment slots for the product in the given time period.
        If a specific user is looking for availability, check their existing appointments as well as the practitioner's.
        Can limit the maximum number of appointment slots returned.
        """
        if limit is not None and limit < 1:
            error_msg = "Limit # availabilities returned must be a positive number."
            log.warning(error_msg)
            raise ValueError(error_msg)

        if not (
            isinstance(start_time, datetime.datetime)
            and isinstance(end_time, datetime.datetime)
        ):
            log.warning(
                "Please provide appropriate search criteria!",
                start_time=start_time,
                end_time=end_time,
                user_id=member.id if member else "unknown",
            )
            return []

        if not self.practitioner_profile.active:
            log.info(
                "No availability for inactive practitioner.",
                practitioner_id=self.practitioner_profile.user_id,
                user_id=member.id if member else "unknown",
            )
            return []

        # Get existing available schedule events
        availabilities = self.get_existing_available_schedule_events(
            start_time, end_time
        )
        if not availabilities:
            log.info(
                "No availability for practitioner without scheduled events.",
                practitioner_id=self.practitioner_profile.user_id,
                user_id=member.id if member else "unknown",
                start_time=start_time,
                end_time=end_time,
            )
            return []

        scheduled_start = self.get_first_scheduled_start_time(
            availabilities[0].starts_at, start_time
        )

        # Calculate first potential appointment end time
        scheduled_end = self.get_scheduled_end_time(scheduled_start)

        # get credits available for member, if any
        all_credits = self.get_all_credits_currently_available(
            scheduled_start, scheduled_end, member
        )

        # Get existing appointments
        existing_appointments = self.get_existing_appointments(
            start_time, end_time, member
        )

        member_has_had_ca_intro_appt = AvailabilityTools.has_had_ca_intro_appointment(
            member
        )

        log.info(
            "AvailabilityCalculator get_availability",
            practitioner_id=self.practitioner_profile.user_id,
            user_id=member.id if member else "unknown",
            start_time=str(start_time),
            end_time=str(end_time),
            n_scheduled_events=len(availabilities),
            member_has_had_ca_intro_appt=member_has_had_ca_intro_appt,
            existing_appointments=existing_appointments,
        )

        # Return full list of potential appointments
        return self.calculate_availability(
            start_time,
            end_time,
            availabilities,
            existing_appointments,
            all_credits,
            member_has_had_ca_intro_appt,
            limit=limit,
            check_daily_intro_capacity=check_daily_intro_capacity,
        )

    @ddtrace.tracer.wrap()
    def calculate_availability(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        availabilities: List[ScheduleEvent],
        existing_appointments: List[Appointment],
        all_credits: List[Credit],
        member_has_had_ca_intro_appt: bool,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        check_daily_intro_capacity: Optional[bool] = True,
    ) -> List[PotentialAppointment]:
        """
        After gathering all data for the product & member & practitioner, calculate possible appointment slots.

        Params:
            -availabilities: sorted list of ScheduleEvents. Sorted in DESCENDING ORDER by `ScheduleEvent.starts_at`
            -member_has_had_ca_intro_appt: used to know whether we are computing availability for a CA intro appt or another type (intro_appts will use CA's daily_intro_capacity, rather than max_capacity)
        """
        appointments = []

        # Calculate first potential appointment start time relative to current time and first scheduled event
        availabilities = [a for a in availabilities if a.ends_at > self.min_start_time]
        if len(availabilities) == 0:
            return appointments
        existing_availabilities = availabilities.copy()
        current_availability = availabilities.pop()
        scheduled_start = self.get_first_scheduled_start_time(
            current_availability.starts_at, start_time
        )

        # Calculate first potential appointment end time
        scheduled_end = self.get_scheduled_end_time(scheduled_start)

        unavailable_dates: list[TimeRange] = []
        if self.assignable_advocate is not None:
            unavailable_dates = self.assignable_advocate.unavailable_dates(
                start_time,
                end_time,
                member_has_had_ca_intro_appt,
                check_daily_intro_capacity,
            )

        # Iterate through all potential appointments after the first, up to the given end of availability.
        cur_offset = 0
        while scheduled_end <= end_time:
            # check if appointment is valid
            potential_appointment = PotentialAppointment(
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                total_available_credits=self.calculate_credits_available_for_appointment(
                    scheduled_start, all_credits
                ),
            )
            has_conflict = self.has_appointment_conflict(
                potential_appointment, existing_appointments, unavailable_dates
            )
            is_available = self.is_within_availabilities(
                potential_appointment, existing_availabilities
            )
            if not has_conflict and is_available:
                if offset is None or cur_offset >= offset:
                    appointments.append(potential_appointment)
                else:
                    cur_offset += 1

                if limit is not None and len(appointments) >= limit:
                    break

            # go to next appointment, shorten the availabilities list, or break
            scheduled_start, scheduled_end = self.compute_next_start_end_time(
                current_start=scheduled_start
            )

            if scheduled_start >= current_availability.ends_at:
                if not availabilities:
                    break

                current_availability = availabilities.pop()
                scheduled_start = current_availability.starts_at
                scheduled_end = self.get_scheduled_end_time(scheduled_start)

        log.info(
            "Computed calculate_availability",
            n_potential_appointments=len(appointments),
            start_time=start_time,
            end_time=end_time,
            n_availabilities=len(existing_availabilities),
            n_existing_appointments=len(existing_appointments),
            n_credits=len(all_credits),
            member_has_had_ca_intro_appt=member_has_had_ca_intro_appt,
            limit=limit,
            offset=offset,
        )
        return appointments

    @staticmethod
    def does_event_occur_on_date(
        date: datetime.datetime,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
    ) -> bool:
        """
        Determine if any part of time range overlaps given date
        """
        return (
            start_time.strftime(DATE_STRING_FORMAT) <= date.strftime(DATE_STRING_FORMAT)
        ) and (
            date.strftime(DATE_STRING_FORMAT) <= end_time.strftime(DATE_STRING_FORMAT)
        )

    @ddtrace.tracer.wrap()
    def has_availability_on_date(
        self,
        date: datetime.datetime,
        availabilities: List[ScheduleEvent],
        existing_appointments: List[Appointment],
        all_credits: List[Credit],
        unavailable_dates: List[TimeRange],
        member_timezone: str = None,  # type: ignore[assignment] # Incompatible default for argument "member_timezone" (default has type "None", argument has type "str")
    ) -> bool:
        """
        Determine if at least one available appointment exists for given date within list of Scheduled Events

        Side Effect: Incoming 'availabilities' argument will be modified to remove any ScheduleEvent instances
        that end prior to provided date. This is done in order to improve performance
        """

        # Create timezone aware datetime object that can be used for comparisons later
        localized_date = get_localized_date(date, "UTC")
        localized_date = localized_date.replace(hour=0, minute=0, second=0)

        for availability in availabilities:
            localized_start_at = get_localized_date(
                availability.starts_at,
                member_timezone,
            )
            localized_end_at = get_localized_date(availability.ends_at, member_timezone)

            # Remove any availability that ends prior to the desired date
            if localized_end_at.strftime(DATE_STRING_FORMAT) < localized_date.strftime(
                DATE_STRING_FORMAT
            ):
                availabilities.remove(availability)
                continue

            # Filter any schedules that aren't at least partially on the current date
            if not self.does_event_occur_on_date(
                date, localized_start_at, localized_end_at
            ):
                continue

            # For availabilities that span multiple days
            potential_start_time = max(localized_start_at, localized_date)
            potential_end_time = self.get_scheduled_end_time(potential_start_time)

            # Keep an appointment time in UTC to keep track of event collisions since
            # unavailable dates/existing appointments are all in UTC
            utc_start_time = availability.starts_at
            utc_end_time = self.get_scheduled_end_time(availability.starts_at)

            while potential_end_time <= localized_end_at:
                # Check that appointment is on correct date if ScheduledEvent overlaps multiple days
                if not self.does_event_occur_on_date(
                    localized_date, potential_start_time, potential_end_time
                ):
                    (
                        potential_start_time,
                        potential_end_time,
                    ) = self.compute_next_start_end_time(
                        current_start=potential_start_time
                    )

                    # keep utc start/end times updated
                    (utc_start_time, utc_end_time) = self.compute_next_start_end_time(
                        current_start=utc_start_time
                    )
                    continue

                potential_appointment = PotentialAppointment(
                    scheduled_start=utc_start_time,
                    scheduled_end=utc_end_time,
                    total_available_credits=self.calculate_credits_available_for_appointment(
                        potential_start_time, all_credits
                    ),
                )
                if not self.has_appointment_conflict(
                    potential_appointment,
                    existing_appointments,
                    unavailable_dates,
                ):
                    return True

                (
                    potential_start_time,
                    potential_end_time,
                ) = self.compute_next_start_end_time(current_start=potential_start_time)

                # keep utc start/end times updated
                (utc_start_time, utc_end_time) = self.compute_next_start_end_time(
                    current_start=utc_start_time
                )

        return False

    @classmethod
    @ddtrace.tracer.wrap()
    def get_all_credits_currently_available(
        cls,
        scheduled_start: datetime.datetime,
        scheduled_end: datetime.datetime,
        member: Optional[User] = None,
    ) -> List[Credit]:
        """Retrieve all credits available for a member to make appointments in this time range."""
        if member is None:
            return []

        available_credits = Credit.available_for_member_time(member.id, scheduled_start)
        return available_credits

    def calculate_credits_available_for_appointment(
        self, scheduled_start: datetime.datetime, available_credits: List[Credit]
    ) -> int:
        """Calculate credits for a given appointment in memory. Credits must remain active through the start time."""
        return sum(
            a.amount
            for a in available_credits
            if a.expires_at is None or (a.expires_at >= scheduled_start)
        )

    @ddtrace.tracer.wrap()
    def get_existing_appointments(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        member: Optional[User] = None,
    ) -> List[Appointment]:
        """Get all unavailable already-reserved appointment slots."""
        prep_time = self.prep_time
        start_time -= datetime.timedelta(minutes=prep_time)
        end_time += datetime.timedelta(minutes=prep_time)

        base = db.session.query(Appointment).filter(
            (
                (
                    (Appointment.scheduled_start <= start_time)
                    & (Appointment.scheduled_end >= end_time)
                )
                | (
                    (Appointment.scheduled_start >= start_time)
                    & (Appointment.scheduled_end >= end_time)
                    & (Appointment.scheduled_start <= end_time)
                )
                | (
                    (Appointment.scheduled_start >= start_time)
                    & (Appointment.scheduled_end <= end_time)
                )
                | (
                    (Appointment.scheduled_start <= start_time)
                    & (Appointment.scheduled_end <= end_time)
                    & (Appointment.scheduled_end >= start_time)
                )
                | (
                    (Appointment.scheduled_start == start_time)
                    & (Appointment.scheduled_end == end_time)
                )
            ),
            Appointment.cancelled_at == None,
        )

        # check for conflicts against all existing provider offerings, not just this product.
        if member and member.schedule:
            existing = base.filter(
                or_(
                    Appointment.product_id.in_(
                        [p.id for p in self.practitioner.products]
                    ),
                    Appointment.member_schedule_id == member.schedule.id,
                )
            ).all()
        else:
            existing = base.filter(
                Appointment.product_id.in_([p.id for p in self.practitioner.products])
            ).all()

        return existing

    @ddtrace.tracer.wrap()
    def get_existing_available_schedule_events(
        self, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> List[ScheduleEvent]:
        """Return available schedule events with the earliest event first."""
        all_availabilities_query = (
            self.practitioner.schedule.existing_events(start_time, end_time)
            .filter(ScheduleEvent.state == ScheduleStates.available)
            .order_by(ScheduleEvent.starts_at.desc())
        )
        return all_availabilities_query.all()

    @ddtrace.tracer.wrap()
    def get_first_scheduled_start_time(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        appointment_starts_at: datetime.datetime,
        range_start_time: datetime.datetime,
    ):
        # any time before now is not actually available, so bump up the started at if it is in the past
        now = datetime.datetime.utcnow()
        buffer_length = datetime.timedelta(
            minutes=max(self.prep_time, self.practitioner_profile.booking_buffer)
        )
        scheduled_start = _bump_datetime_by_increment(
            range_start_time, now, buffer_length
        )

        # if the earliest scheduled event available is greater than the start time, bump up the start time more
        if scheduled_start < appointment_starts_at:
            scheduled_start = appointment_starts_at

        return scheduled_start

    def get_scheduled_end_time(
        self, scheduled_start: datetime.datetime
    ) -> datetime.datetime:
        # Note use of product length, not buffered length
        return scheduled_start + datetime.timedelta(minutes=self.product.minutes)

    def has_appointment_conflict(
        self,
        potential_appointment: PotentialAppointment,
        existing_appointments: List[Appointment],
        unavailable_dates: List[TimeRange],
    ) -> bool:
        if is_in_date_ranges(potential_appointment.scheduled_start, unavailable_dates):
            return True

        return any(
            existing_appt.contains(potential_appointment, prep=self.prep_time)
            for existing_appt in existing_appointments
        )

    def compute_next_start_end_time(
        self, current_start: datetime.datetime
    ) -> tuple[datetime.datetime, datetime.datetime]:
        next_start = current_start + datetime.timedelta(minutes=self.padded_length)
        next_end = self.get_scheduled_end_time(next_start)

        return next_start, next_end

    def is_within_availabilities(
        self,
        potential_appointment: PotentialAppointment,
        existing_availabilities: List[ScheduleEvent],
    ) -> bool:
        """
        Checks if `existing_availabilities` includes a contiguous block of ScheduleEvents
        that fully contains `potential_appointment`
        """
        scheduled_start = potential_appointment.scheduled_start
        scheduled_end = potential_appointment.scheduled_end

        # Filter for only the schedule events that could be used to contain the appointment
        possible = [
            a
            for a in existing_availabilities
            if a.starts_at <= scheduled_end and a.ends_at >= scheduled_start
        ]
        possible = sorted(possible, key=lambda a: a.starts_at)

        if not possible:  # No schedule events
            return False

        # This loop checks that there's a contiguous block of schedule events that contains
        # the time range (scheduled_start, scheduled_end)
        # In order to have a containing block of schedule events, we need:
        # 1. `schedule_start` must be included in one of the events
        # 2. All events must be contiguous. Specifically: events[i].ends_at <= events[i+1].starts_at
        # 3. `scheduled_end` must be included in one of the events
        contains_start = False
        for i in range(len(possible)):
            event = possible[i]
            if not contains_start:
                # Check if `scheduled_start` is contained within this schedule event
                if event.starts_at <= scheduled_start < event.ends_at:
                    contains_start = True
                elif event.starts_at > scheduled_start:
                    return False

            if contains_start and event.ends_at >= scheduled_end:
                return True

            # If we've reached the end of `possible` without reaching `scheduled_end`,
            # then we don't have availability
            if i + 1 >= len(possible):
                return False

            # Check for a gap between the current and next events
            next_event = possible[i + 1]
            if next_event.starts_at > event.ends_at:
                return False

        return False


@dataclass
class PotentialAvailability:
    __slots__ = ("id", "minimum_appointment_interval", "availability")
    id: int
    minimum_appointment_interval: float
    availability: List[PotentialAppointment]


@dataclass
class PotentialMassAvailability:
    __slots__ = ("id", "product_id", "minimum_appointment_interval", "availability")
    id: int
    product_id: int
    minimum_appointment_interval: float
    availability: List[TimeRange]


@dataclass
class PotentialPractitionerAvailabilities:
    __slots__ = (
        "practitioner_id",
        "product_id",
        "product_price",
        "duration",
        "availabilities",
        "contract_priority",
    )
    practitioner_id: int
    product_id: int
    product_price: float
    duration: int
    availabilities: List[PotentialAppointment]
    contract_priority: int


class MassAvailabilityCalculator:
    @ddtrace.tracer.wrap()
    def get_mass_availability(
        self,
        practitioner_profiles: List[PractitionerProfile],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        member: Optional[User] = None,
    ) -> List[PotentialMassAvailability]:
        # Get schedules and booked appointments for practitioners
        (
            all_existing_availabilities,
            all_existing_appointments,
            member_appointments,
            all_credits,
        ) = self.get_common_availability_fields(
            practitioner_profiles=practitioner_profiles,
            start_time=start_time,
            end_time=end_time,
            member=member,
        )

        all_availabilities = []

        member_has_had_ca_intro_appt = AvailabilityTools.has_had_ca_intro_appointment(
            member
        )

        log.info(
            "MassAvailabilityCalculator get_mass_availability",
            practitioner_ids=[pp.user_id for pp in practitioner_profiles],
            user_id=member.id if member else "unknown",
            start_time=start_time,
            end_time=end_time,
            member_has_had_ca_intro_appt=member_has_had_ca_intro_appt,
            n_scheduled_events=len(all_existing_availabilities),
            existing_appointments=all_existing_appointments,
        )

        for profile in practitioner_profiles:
            # TODO: Make same performance improvement here as we did in get_practitioner_availabilities,
            #  where we query all products outside of for loop

            product = AvailabilityTools.get_product_for_practitioner(profile)
            # get the specific data for this practitioner & filter to active products
            availability = all_existing_availabilities.get(profile.user_id) or []
            if not product or not availability:
                continue
            existing_appointments = all_existing_appointments.get(profile.user_id) or []
            existing_appointments += member_appointments
            # TODO: does this +timedelta make sense if the start time is not now()? (currently always now())
            practitioner_start_time = start_time + datetime.timedelta(
                minutes=profile.booking_buffer
            )

            calculator = AvailabilityCalculator(profile, product)
            all_potential_availabilities = calculator.calculate_availability(
                practitioner_start_time,
                end_time,
                availability,
                existing_appointments,
                all_credits,
                member_has_had_ca_intro_appt,
            )
            calculated_availability_ranges = self.generate_availability(
                all_potential_availabilities
            )
            all_availabilities.append(
                PotentialMassAvailability(
                    id=profile.user_id,
                    product_id=product.id,
                    minimum_appointment_interval=calculator.padded_length,
                    availability=calculated_availability_ranges,
                )
            )

        return all_availabilities

    @ddtrace.tracer.wrap()
    def get_practitioner_available_dates(
        self,
        practitioner_profiles: List[PractitionerProfile],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        member: Optional[User] = None,
        vertical_name: Optional[str] = None,
        member_timezone: str = None,  # type: ignore[assignment] # Incompatible default for argument "member_timezone" (default has type "None", argument has type "str")
    ) -> List[dict]:
        start_time.replace(tzinfo=None)
        end_time.replace(tzinfo=None)

        # Get schedules and booked appointments for practitioners
        (
            all_existing_scheduled_events,
            all_existing_appointments,
            member_appointments,
            all_credits,
        ) = self.get_common_availability_fields(
            practitioner_profiles=practitioner_profiles,
            # Add one day buffer to beginning and end of search range and set time value to scan for schedules
            # happening at any point on those days
            start_time=(start_time - datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            ),
            end_time=(end_time + datetime.timedelta(days=1)).replace(
                hour=23, minute=59, second=59
            ),
            member=member,
        )

        member_has_had_ca_intro_appt = AvailabilityTools.has_had_ca_intro_appointment(
            member
        )

        # Bundle availabilities with appointments and calculator instance
        availability_map = {}

        for profile in practitioner_profiles:
            product = AvailabilityTools.get_product_for_practitioner(
                profile, vertical_name=vertical_name
            )
            if not product:
                continue

            # get the specific data for this practitioner & filter to active products
            availabilities = all_existing_scheduled_events.get(profile.user_id) or []
            if not availabilities:
                continue

            existing_appointments = all_existing_appointments.get(profile.user_id) or []
            existing_appointments += member_appointments
            calculator = AvailabilityCalculator(profile, product)

            unavailable_dates = []
            if calculator.assignable_advocate is not None:
                unavailable_dates = calculator.assignable_advocate.unavailable_dates(
                    start_time, end_time, member_has_had_ca_intro_appt
                )

            practitioner_availability_map = partition_events_by_localized_date(
                event_list=availabilities,
                start_str="starts_at",
                end_str="ends_at",
                member_timezone=member_timezone,
            )
            practitioner_appointment_map = partition_events_by_localized_date(
                event_list=existing_appointments,
                start_str="scheduled_start",
                end_str="scheduled_end",
                member_timezone=member_timezone,
            )

            for (
                date,
                availability_for_date,
            ) in practitioner_availability_map.items():
                appointments_for_date = practitioner_appointment_map.get(date, [])
                date_map = availability_map.get(date, [])
                date_map.append(
                    (
                        availability_for_date,
                        appointments_for_date,
                        calculator,
                        unavailable_dates,
                    )
                )
                availability_map[date] = date_map

        available_dates = []
        iter_date = start_time

        # determine if any practitioner has availability for each date
        while iter_date <= end_time:
            iter_date_str = iter_date.strftime(DATE_STRING_FORMAT)
            availability_result = {"date": iter_date_str, "hasAvailability": False}

            availability_mappings = availability_map.get(iter_date_str)
            if availability_mappings:
                for (
                    practitioner_availability,
                    practitioner_appointments,
                    practitioner_calculator,
                    unavailable_dates,
                ) in availability_mappings:
                    is_practitioner_available = (
                        practitioner_calculator.has_availability_on_date(
                            date=iter_date,
                            availabilities=practitioner_availability,
                            existing_appointments=practitioner_appointments,
                            all_credits=all_credits,
                            unavailable_dates=unavailable_dates,
                            member_timezone=member_timezone,
                        )
                    )
                    if is_practitioner_available:
                        availability_result["hasAvailability"] = True
                        break

            available_dates.append(availability_result)
            iter_date += datetime.timedelta(days=1)

        return available_dates

    @ddtrace.tracer.wrap()
    def get_practitioner_availabilities(
        self,
        practitioner_profiles: List[PractitionerProfile],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        limit: int,
        offset: int,
        vertical_name: Optional[str] = None,
        member: Optional[User] = None,
        contract_priority_by_practitioner_id: Optional[dict[int, int]] = None,
    ) -> List[PotentialPractitionerAvailabilities]:
        # Get schedules and booked appointments for practitioners
        (
            all_existing_availabilities,
            all_existing_appointments,
            member_appointments,
            all_credits,
        ) = self.get_common_availability_fields(
            practitioner_profiles=practitioner_profiles,
            start_time=start_time,
            end_time=end_time,
            member=member,
        )

        member_has_had_ca_intro_appt = AvailabilityTools.has_had_ca_intro_appointment(
            member
        )

        all_availabilities = []

        # TODO: here we query products to use the product data (mostly length) when computing availabilities
        # If we could know in advance that we are computing availabilities for an intro appointment (which is the case when building the pooled calendar)
        # then we can stop querying the products and just hardcode the product length as we know its fixed.
        min_price_products = (
            AvailabilityTools.get_lowest_price_products_for_practitioners(
                practitioner_profiles, vertical_name=vertical_name
            )
        )

        for profile in practitioner_profiles:
            product = (
                min_price_products[profile.user_id]  # type: ignore[index]
                if profile.user_id in min_price_products
                else None
            )

            if not product:
                continue

            # get the specific data for this practitioner & filter to active products

            availability = all_existing_availabilities.get(profile.user_id) or []

            if not availability:
                all_availabilities.append(
                    PotentialPractitionerAvailabilities(
                        practitioner_id=profile.user_id,
                        product_id=product.id,
                        product_price=product.price,
                        duration=product.minutes,
                        availabilities=[],
                        contract_priority=99,
                    )
                )
                continue

            existing_appointments = all_existing_appointments.get(profile.user_id) or []
            existing_appointments += member_appointments
            # TODO: does adding booking_buffer always make sense, even if start_time is not now?
            practitioner_start_time = (
                AvailabilityTools.pad_and_round_availability_start_time(
                    start_time, profile.booking_buffer, profile.rounding_minutes
                )
            )

            calculator = AvailabilityCalculator(
                profile, product, load_practitioner_user_entity=False
            )
            # Note: Heads up, the `availability` var seems to change after this call. Would be nice to stop that from happening.
            all_potential_availabilities = calculator.calculate_availability(
                practitioner_start_time,
                end_time,
                availability,
                existing_appointments,
                all_credits,
                member_has_had_ca_intro_appt,
                limit=limit,
                offset=offset,
            )
            all_availabilities.append(
                PotentialPractitionerAvailabilities(
                    practitioner_id=profile.user_id,
                    product_id=product.id,
                    product_price=product.price,
                    duration=product.minutes,
                    availabilities=all_potential_availabilities,
                    contract_priority=(
                        contract_priority_by_practitioner_id.get(profile.user_id, 99)
                        if contract_priority_by_practitioner_id
                        else 99
                    ),
                )
            )

        return all_availabilities

    @ddtrace.tracer.wrap()
    # TODO: revisit opportunities for improvement here, currently these queries are not fast
    def get_common_availability_fields(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        practitioner_profiles: List[PractitionerProfile],
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        member: Optional[User] = None,
    ):
        practitioner_ids = [p.user_id for p in practitioner_profiles]
        # Get schedules for practitioners
        all_existing_scheduled_events = (
            self.get_mass_existing_available_schedule_events(
                start_time, end_time, practitioner_ids
            )
        )

        # Get booked appointments
        (
            all_existing_appointments,
            member_appointments,
        ) = self.get_mass_existing_appointments(
            start_time, end_time, practitioner_ids, member
        )

        all_credits = AvailabilityCalculator.get_all_credits_currently_available(
            start_time, end_time, member
        )

        return (
            all_existing_scheduled_events,
            all_existing_appointments,
            member_appointments,
            all_credits,
        )

    def generate_availability(self, all_potential_availabilities) -> List[TimeRange]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        # given that we currently return an appointment's buffered_length without booking buffer to calculate segments
        # the gap between segments should be zero, not profile.booking_buffer
        # If we start integrating the booking buffer between each appointment, take that into account here.
        allowed_gap = 0  # datetime.timedelta(minutes=booking_buffer).total_seconds()
        contiguous_availability = TimeRange(None, None)
        for time_slot in all_potential_availabilities:
            if (
                contiguous_availability.start_time is None
                and contiguous_availability.end_time is None
            ):
                # New time range, fill in the minimum start and end with the current time slot data
                contiguous_availability.start_time = time_slot.scheduled_start
                contiguous_availability.end_time = time_slot.scheduled_end
            elif (
                time_slot.scheduled_start - contiguous_availability.end_time
            ).total_seconds() > allowed_gap:
                # previous time range has ended, but the next is not contiguous.
                yield contiguous_availability
                contiguous_availability = TimeRange(
                    time_slot.scheduled_start, time_slot.scheduled_end
                )
            else:
                # current time range continues, match the end time to the current time slot end
                contiguous_availability.end_time = time_slot.scheduled_end
        if (
            contiguous_availability.start_time is not None
            and contiguous_availability.end_time is not None
        ):
            # append the last contiguous_availability if necessary
            yield contiguous_availability

    @classmethod
    def get_mass_existing_available_schedule_events(
        cls,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        user_ids: List[int],
    ) -> defaultdict:
        """Get available appointment slots."""
        events_query = (
            db.session.query(ScheduleEvent, Schedule.user_id)
            .join(Schedule)
            .filter(Schedule.user_id.in_(user_ids))
            .filter(
                (
                    (
                        (ScheduleEvent.starts_at <= start_time)
                        & (ScheduleEvent.ends_at >= end_time)
                    )
                    | (
                        (ScheduleEvent.starts_at >= start_time)
                        & (ScheduleEvent.ends_at >= end_time)
                        & (ScheduleEvent.starts_at <= end_time)
                    )
                    | (
                        (ScheduleEvent.starts_at >= start_time)
                        & (ScheduleEvent.ends_at <= end_time)
                    )
                    | (
                        (ScheduleEvent.starts_at <= start_time)
                        & (ScheduleEvent.ends_at <= end_time)
                        & (ScheduleEvent.ends_at >= start_time)
                    )
                )
            )
            .filter(ScheduleEvent.state == ScheduleStates.available)
            .order_by(ScheduleEvent.starts_at.desc())
        )

        events = events_query.all()

        all_available_events = defaultdict(list)
        for event, user_id in events:
            all_available_events[user_id].append(event)
        return all_available_events

    @classmethod
    def get_mass_existing_appointments(
        cls,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        provider_ids: list[int],
        member: User | None = None,
    ) -> tuple[defaultdict, list]:
        """Get all unavailable already-reserved appointment slots."""
        if member:
            # Select the first non-null value from the product's prep_buffer,
            # then the practitioner's. Falls back to 0 if none are found
            prep_time_str = text(
                "INTERVAL COALESCE(product.prep_buffer, practitioner_profile.default_prep_buffer, 0) MINUTE"
            )
            prepped_start = func.subdate(start_time, prep_time_str)
            prepped_end = func.adddate(end_time, prep_time_str)
            base = (
                db.session.query(Appointment, Product.user_id)
                .join(Product)
                .join(
                    PractitionerProfile, Product.user_id == PractitionerProfile.user_id
                )
                .filter(
                    Appointment.scheduled_start
                    >= start_time - APPOINTMENT_SEARCH_BUFFER,
                    Appointment.scheduled_end <= end_time + APPOINTMENT_SEARCH_BUFFER,
                    (
                        (
                            (Appointment.scheduled_start <= prepped_start)
                            & (Appointment.scheduled_end >= prepped_end)
                        )
                        | (
                            (Appointment.scheduled_start >= prepped_start)
                            & (Appointment.scheduled_end >= prepped_end)
                            & (Appointment.scheduled_start <= prepped_end)
                        )
                        | (
                            (Appointment.scheduled_start >= prepped_start)
                            & (Appointment.scheduled_end <= prepped_end)
                        )
                        | (
                            (Appointment.scheduled_start <= prepped_start)
                            & (Appointment.scheduled_end <= prepped_end)
                            & (Appointment.scheduled_end >= prepped_start)
                        )
                    ),
                    Appointment.cancelled_at == None,
                )
            )

        else:
            base = (
                db.session.query(Appointment, Product.user_id)
                .join(Product)
                .filter(
                    Appointment.scheduled_start
                    >= start_time - APPOINTMENT_SEARCH_BUFFER,
                    Appointment.scheduled_end <= end_time + APPOINTMENT_SEARCH_BUFFER,
                    (
                        (
                            (Appointment.scheduled_start <= start_time)
                            & (Appointment.scheduled_end >= end_time)
                        )
                        | (
                            (Appointment.scheduled_start >= start_time)
                            & (Appointment.scheduled_end >= end_time)
                            & (Appointment.scheduled_start <= end_time)
                        )
                        | (
                            (Appointment.scheduled_start >= start_time)
                            & (Appointment.scheduled_end <= end_time)
                        )
                        | (
                            (Appointment.scheduled_start <= start_time)
                            & (Appointment.scheduled_end <= end_time)
                            & (Appointment.scheduled_end >= start_time)
                        )
                    ),
                    Appointment.cancelled_at == None,
                )
            )

        # check for conflicts against:
        # 1. all existing provider offerings, not just this product
        # 2. or: the member's existing appointments with other practitioners (if member was provided)
        filter_statement = Product.user_id.in_(provider_ids)
        if member and member.schedule:
            filter_statement = or_(
                Product.user_id.in_(provider_ids),
                Appointment.member_schedule_id == member.schedule.id,
            )
        existing = base.filter(filter_statement).all()

        user_ids_set = set(provider_ids)
        all_existing_appointments = defaultdict(list)
        member_appointments = []
        for appointment, practitioner_id in existing:
            if practitioner_id in user_ids_set:
                all_existing_appointments[practitioner_id].append(appointment)

            if (
                member
                and member.schedule
                and appointment.member_schedule_id == member.schedule.id
                # Filter out member appointments which have been picked up due to prep buffer
                and appointment.scheduled_start >= start_time
                and appointment.scheduled_end <= end_time
            ):
                member_appointments.append(appointment)

        return all_existing_appointments, member_appointments


def is_in_date_ranges(
    date: datetime.datetime,
    date_ranges: list[TimeRange],
) -> bool:
    return any(d.start_time <= date <= d.end_time for d in date_ranges)


def _bump_datetime_by_increment(
    dt: datetime.datetime,
    target_time: datetime.datetime,
    increment_length: datetime.timedelta,
) -> datetime.datetime:
    """Bumps a datetime to be equal to or after a target datetime"""
    if dt >= target_time or not increment_length:
        return dt

    else:
        diff = target_time - dt
        multiple = diff / increment_length  # Find the num of increments needed

        # Round up and add to the start time
        return dt + (math.ceil(multiple) * increment_length)


def get_localized_date(date: datetime.datetime, timezone: str | None = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    tz = pytz.timezone(DEFAULT_TIMEZONE)
    if timezone in pytz.all_timezones:
        tz = pytz.timezone(timezone)

    localized_offset = tz.localize(date).utcoffset()
    return date + localized_offset


def partition_events_by_localized_date(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    event_list: List[Any], start_str: str, end_str: str, member_timezone: str = None  # type: ignore[assignment] # Incompatible default for argument "member_timezone" (default has type "None", argument has type "str")
):
    date_map = {}

    for event in event_list:
        localized_event_start = get_localized_date(
            getattr(event, start_str), member_timezone
        )

        # set time to end of day in case the event spans multiple days
        localized_event_end = get_localized_date(
            getattr(event, end_str), member_timezone
        ).replace(hour=23, minute=59, second=59)

        while localized_event_start < localized_event_end:
            localized_start_str = localized_event_start.strftime(DATE_STRING_FORMAT)
            event_list = date_map.get(localized_start_str, [])
            event_list.append(event)
            date_map[localized_start_str] = event_list
            localized_event_start = localized_event_start + datetime.timedelta(days=1)

    return date_map
