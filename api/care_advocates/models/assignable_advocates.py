from __future__ import annotations

import datetime
import random
from collections import Counter, defaultdict, namedtuple
from operator import attrgetter
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from ddtrace import tracer
from maven.feature_flags import bool_variation
from pytz import UTC, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    and_,
    func,
    or_,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Load, Query, joinedload, load_only, relationship, validates

from appointments.models.appointment import Appointment
from appointments.utils.booking import MassAvailabilityCalculator, TimeRange
from authn.models.user import User
from care_advocates.models.member_match_logs import MemberMatchLog
from common import stats
from health.data_models.risk_flag import RiskFlag
from models import base
from models.base import db
from models.profiles import (
    CareTeamTypes,
    Language,
    MemberPractitionerAssociation,
    PractitionerProfile,
    practitioner_languages,
)
from utils import braze
from utils.log import logger

log = logger(__name__)

_START_KEY = "vacation_started_at"
_END_KEY = "vacation_ended_at"

DEFAULT_CARE_COORDINATOR_EMAIL = "kaitlyn+messaging@mavenclinic.com"

THREE_DAYS = "3_days"
SEVEN_DAYS = "7_days"
SEVEN_DAYS_CATCH_ALL = "7_days_catch_all"

AMAZON_US_ORG_ID = 2441


class AssignableAdvocate(base.TimeLoggedModelBase):
    __tablename__ = "assignable_advocate"

    practitioner_id = Column(
        Integer, ForeignKey("practitioner_profile.user_id"), primary_key=True
    )
    marketplace_allowed = Column(Boolean, nullable=False, default=True)
    vacation_started_at = Column(DateTime)
    vacation_ended_at = Column(DateTime)

    practitioner = relationship("PractitionerProfile")
    max_capacity = Column(SmallInteger, nullable=False)
    daily_intro_capacity = Column(SmallInteger, nullable=False)

    @property
    def admin_name(self) -> str:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return f"[{self.practitioner_id}] {self.practitioner.user.full_name}"

    @property
    def admin_assignments(self) -> str:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        assignments = []
        if self.marketplace_allowed:
            assignments.append("marketplace")
        if assignments:
            return " \u2022 ".join(assignments)
        return "no assignments"

    @property
    def admin_vacation(self) -> str:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        receiving_patients = "receiving patients"
        starting_vacation_for_in = "{} days vacation starting in {} days"
        starting_vacation_in = "on vacation forever starting in {} days"
        on_vacation_for = "{} more days of vacation"
        on_vacation_forever = "on vacation forever"
        now = datetime.datetime.utcnow()
        today = now.date()
        start_date = self.vacation_started_at and self.vacation_started_at.date()
        end_date = self.vacation_ended_at and self.vacation_ended_at.date()
        if self.vacation_started_at and self.vacation_ended_at:
            if now < self.vacation_started_at:
                return starting_vacation_for_in.format(
                    (end_date - start_date).days, (start_date - today).days
                )
            if now < self.vacation_ended_at:
                return on_vacation_for.format((end_date - today).days)
            return receiving_patients
        if self.vacation_started_at:
            if now < self.vacation_started_at:
                return starting_vacation_in.format((start_date - today).days)
            return on_vacation_forever
        if self.vacation_ended_at:
            if now < self.vacation_ended_at:
                return on_vacation_for.format((end_date - today).days)
            return receiving_patients
        return receiving_patients

    @validates("practitioner")
    def practitioner_must_be_advocate(self, _key, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if field.user.is_care_coordinator:
            return field
        raise ValueError("Practitioner must be a care advocate.")

    @validates(_START_KEY, _END_KEY)
    def validate_start_before_end(self, key, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        start = field if key == _START_KEY else self.vacation_started_at
        # don't use #self.vacation_ended_at; old values will trigger errors
        end = field if key == _END_KEY else None
        if start is None or end is None or start < end:
            return field  # okay
        other_key = {_START_KEY: _END_KEY, _END_KEY: _START_KEY}[key]
        raise ValueError(
            f"Cannot record featured practitioner {key} in conflict with {other_key}."
        )

    @tracer.wrap()
    def unavailable_dates(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        start_date,
        end_date,
        member_has_had_ca_intro_appt,
        check_daily_intro_capacity=True,
    ) -> List[TimeRange]:
        dates = self.calculate_unavailable_dates_vacation()
        dates += self.calculate_unavailable_dates_limited_capacity(
            start_date,
            end_date,
            member_has_had_ca_intro_appt,
            check_daily_intro_capacity,
        )
        sorted_dates = sort_and_merge_dates(dates)
        log.info(
            "Computed unavailable_dates",
            practitioner_id=self.practitioner_id,
            unavailable_dates=sorted_dates,
            start_date=str(start_date),
            end_date=str(end_date),
            member_has_had_ca_intro_appt=member_has_had_ca_intro_appt,
        )

        return sorted_dates

    @tracer.wrap()
    def calculate_unavailable_dates_limited_capacity(
        self,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        member_has_had_ca_intro_appt: bool,
        check_daily_intro_capacity: bool = True,
    ) -> List[TimeRange]:
        """
        Return list of days where CA has met their capacity, aka, days where they already have enough booked appointments.
        If the member is booking an intro appointment, in addition to the max_capacity check include a daily_intro_capacity check.
        """

        # If practitioner has no capacity, they are unavailable for the full range of dates
        if self.max_capacity == 0 or (
            not member_has_had_ca_intro_appt
            and check_daily_intro_capacity
            and self.daily_intro_capacity == 0
        ):
            log.info(
                "CA with no capacity, will include full range of dates as not available",
                practitioner_id=self.practitioner_id,
                start_date=str(start_date),
                end_date=str(end_date),
                member_has_had_ca_intro_appt=member_has_had_ca_intro_appt,
                check_daily_intro_capacity=check_daily_intro_capacity,
                max_capacity=self.max_capacity,
                daily_intro_capacity=self.daily_intro_capacity,
            )
            return [TimeRange(start_time=start_date, end_time=end_date)]

        prac_tz = timezone(
            db.session.query(User.timezone)
            .filter_by(id=self.practitioner_id)
            .first()[0]
        )
        start_date = UTC.localize(start_date)
        end_date = UTC.localize(end_date)

        # Count number of appointments per day in the practitioners timezone,
        # and consider as unavailable the days where the number of appointments is >= than CA's capacity
        # Appointment.scheduled_start will come back from the DB as naive, but they are in UTC.
        # We will count based on practitioners timezone
        all_appointments_from_range = (
            Appointment.appointments_from_date_range(
                self.practitioner_id,
                start_date.astimezone(prac_tz),
                end_date.astimezone(prac_tz),
            )
            .options(load_only("scheduled_start"))
            .all()
        )
        if len(all_appointments_from_range) == 0:
            log.info(
                "No appointments in date range. No days marked as unavailable",
                user_id=self.practitioner_id,
                start_date=str(start_date),
                end_date=str(end_date),
            )
            return []
        log.info(
            "Got appointments in date range",
            appointments_ids=[a.id for a in all_appointments_from_range],
            user_id=self.practitioner_id,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        n_all_appointments = Counter(
            UTC.localize(a.scheduled_start).astimezone(prac_tz).date()
            for a in all_appointments_from_range
        )
        log.info(
            "Computed n_all_appointments",
            n_all_appointments=str(dict(n_all_appointments)),
            prac_tz=str(prac_tz),
            appointments_ids=[a.id for a in all_appointments_from_range],
            user_id=self.practitioner_id,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        n_intro_appointments = None
        # Count n of intro appts only if the member has not had an intro appt and we want to check daily intro capacity
        if not member_has_had_ca_intro_appt and check_daily_intro_capacity:
            intro_appointments_from_range = (
                Appointment.intro_appointments_from_date_range(
                    self.practitioner_id,
                    start_date.astimezone(prac_tz),
                    end_date.astimezone(prac_tz),
                )
            )
            if len(intro_appointments_from_range) == 0:
                log.info(
                    "No intro appointments in date range",
                    user_id=self.practitioner_id,
                    start_date=str(start_date),
                    end_date=str(end_date),
                )
            else:
                log.info(
                    "Got intro appointments in date range",
                    appointments_ids=[a.id for a in intro_appointments_from_range],
                    start_date=str(start_date),
                    end_date=str(end_date),
                    user_id=self.practitioner_id,
                )
                n_intro_appointments = Counter(
                    UTC.localize(a.scheduled_start).astimezone(prac_tz).date()
                    for a in intro_appointments_from_range
                )
                log.info(
                    "Computed n_intro_appointments",
                    n_intro_appointments=str(dict(n_intro_appointments)),
                    prac_tz=str(prac_tz),
                    start_date=str(start_date),
                    end_date=str(end_date),
                    user_id=self.practitioner_id,
                )

        # Look over every day and check if max_capcity (and daily_intro_capacity if trying to book intro appt) are met
        unavailable_dates = []
        for date in n_all_appointments.keys():
            max_capacity_met = False
            daily_intro_capacity_met = None

            if n_all_appointments[date] >= self.max_capacity:
                max_capacity_met = True

            if n_intro_appointments:
                daily_intro_capacity_met = (
                    date in n_intro_appointments
                    and n_intro_appointments[date] >= self.daily_intro_capacity
                )

            if max_capacity_met or daily_intro_capacity_met:
                # Block the whole day from start to end of day
                start_datetime = prac_tz.localize(
                    datetime.datetime.combine(date, datetime.datetime.min.time())
                )
                end_datetime = prac_tz.localize(
                    datetime.datetime.combine(date, datetime.datetime.max.time())
                )

                # Convert to UTC and remove timezone as the overall system is timezone naive
                start_datetime = start_datetime.astimezone(UTC).replace(tzinfo=None)
                end_datetime = end_datetime.astimezone(UTC).replace(tzinfo=None)

                log.info(
                    "Adding date to unavailable_dates, date is capacity restricted",
                    date=date,
                    start_datetime_utc=str(start_datetime),
                    end_datetime_utc=str(end_datetime),
                    max_capacity_met=max_capacity_met,
                    daily_intro_capacity_met=daily_intro_capacity_met,
                    prac_tz=prac_tz,
                    user_id=self.practitioner_id,
                    daily_intro_capacity=self.daily_intro_capacity,
                    max_capacity=self.max_capacity,
                    n_total_appts=n_all_appointments[date],
                    member_has_had_ca_intro_appt=member_has_had_ca_intro_appt,
                    check_daily_intro_capacity=check_daily_intro_capacity,
                    n_intro_appts=n_intro_appointments
                    and date in n_intro_appointments
                    and n_intro_appointments[date],
                )

                unavailable_dates.append(
                    TimeRange(start_time=start_datetime, end_time=end_datetime)
                )

            else:
                log.info(
                    "Not adding date to unavailable_dates, no capacity restriction applies",
                    date=str(date),
                    max_capacity_met=max_capacity_met,
                    daily_intro_capacity_met=daily_intro_capacity_met,
                    prac_tz=prac_tz,
                    user_id=self.practitioner_id,
                    daily_intro_capacity=self.daily_intro_capacity,
                    max_capacity=self.max_capacity,
                    n_total_appts=n_all_appointments[date],
                    member_has_had_ca_intro_appt=member_has_had_ca_intro_appt,
                    check_daily_intro_capacity=check_daily_intro_capacity,
                    n_intro_appts=n_intro_appointments
                    and date in n_intro_appointments
                    and n_intro_appointments[date],
                )
        return unavailable_dates

    @tracer.wrap()
    def calculate_unavailable_dates_max_capacity(
        self, start_date: datetime.datetime, end_date: datetime.datetime
    ) -> List[TimeRange]:
        # TODO: we dont seem to have any test cases that touches these lines coming down here
        # My guess is that all the test cases we have for unavailable_dates() were reutilized to work with the load balancing ff, but now we dont have any tests for when ff is off
        dates = []
        if self.max_capacity == 0:
            dates.append(TimeRange(start_time=start_date, end_time=end_date))
        else:
            prac_tz = timezone(
                db.session.query(User.timezone)
                .filter_by(id=self.practitioner_id)
                .first()[0]
            )
            appointments_from_range = Appointment.appointments_from_date_range(
                self.practitioner_id,
                start_date.astimezone(prac_tz),  # type: ignore[attr-defined] # datetime? has no attribute "astimezone"
                end_date.astimezone(prac_tz),  # type: ignore[attr-defined] # datetime? has no attribute "astimezone"
            ).options(load_only("scheduled_start"))

            if appointments_from_range:
                # Appointment.scheduled_start will come back from the DB as naive, but they are in UTC
                appointments_by_date = Counter(
                    UTC.localize(a.scheduled_start).astimezone(prac_tz).date()
                    for a in appointments_from_range
                )
                log.info(
                    "appointments_by_date computed",
                    appointments_by_date=str(dict(appointments_by_date)),
                    start_date=str(start_date),
                    end_date=str(end_date),
                    prac_tz=str(prac_tz),
                    user_id=self.practitioner_id,
                )
                for date, count in appointments_by_date.items():
                    if self.max_capacity is not None and count >= self.max_capacity:
                        start_datetime = prac_tz.localize(
                            datetime.datetime.combine(
                                date, datetime.datetime.min.time()
                            )
                        )
                        end_datetime = prac_tz.localize(
                            datetime.datetime.combine(
                                date, datetime.datetime.max.time()
                            )
                        )

                        # Convert to UTC and remove timezone as the rest of the system timezone naive
                        start_datetime = start_datetime.astimezone(UTC).replace(
                            tzinfo=None
                        )
                        end_datetime = end_datetime.astimezone(UTC).replace(tzinfo=None)

                        dates.append(
                            TimeRange(start_time=start_datetime, end_time=end_datetime)
                        )
                        log.info(
                            "Adding date to list of unavailable_dates",
                            date=date,
                            start_datetime_utc=str(start_datetime),
                            end_datetime_utc=str(end_datetime),
                            prac_tz=str(prac_tz),
                            user_id=self.practitioner_id,
                            appointments_count=count,
                            max_capacity=self.max_capacity,
                        )

        return dates

    @tracer.wrap()
    def calculate_unavailable_dates_vacation(self) -> List[TimeRange]:
        dates = []
        if self.vacation_started_at and self.vacation_ended_at:
            dates.append(
                TimeRange(
                    start_time=self.vacation_started_at, end_time=self.vacation_ended_at
                )
            )
        return dates

    @classmethod
    def default_care_coordinator(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            db.session.query(User)
            .filter(User.email == DEFAULT_CARE_COORDINATOR_EMAIL)
            .options(
                joinedload(User.practitioner_profile).joinedload(
                    PractitionerProfile.verticals
                )
            )
            .one_or_none()
        )

    @classmethod
    def any_user_flags_match_eligible_risk_flags(
        cls, risk_flags: Iterable[RiskFlag]
    ) -> bool:
        from health.services.care_coaching_eligibility_service import (
            ELIGIBLE_PREGNANCY_RISK_FLAGS,
        )

        return any(
            r for r in risk_flags if r and r.name in ELIGIBLE_PREGNANCY_RISK_FLAGS
        )

    @classmethod
    @tracer.wrap()
    def log_with_matched_ca(
        cls,
        user: User,
        ca_id: int,
        user_flags: Iterable[RiskFlag],
        logs_to_emit: list[str],
    ) -> None:
        # We want to emit these saved logs together with some information about the eventual matched CA
        ca_name = (
            db.session.query(PractitionerProfile.full_name)
            .filter(PractitionerProfile.user_id == ca_id)
            .scalar()
        )

        user_flags_are_eligible = cls.any_user_flags_match_eligible_risk_flags(
            user_flags
        )
        user_is_from_amazon = (
            user.organization and user.organization.id == AMAZON_US_ORG_ID
        )

        for log_to_emit in logs_to_emit:
            log.warning(
                f"logged with matched ca - {log_to_emit}",
                user_id=user.id,
                country=user.country and user.country.alpha_2,
                organization=user.organization,
                track=user.current_member_track.name,
                user_flags=user_flags,
                ca_name=ca_name,
                ca_id=ca_id,
                user_is_from_amazon=user_is_from_amazon,
                user_flags_are_eligible=user_flags_are_eligible,
            )

    @classmethod
    @tracer.wrap()
    def add_care_coordinator_for_member(cls, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        # import here to avoid circular import
        from tasks.braze import update_care_advocate_attrs
        from tracks.service import TrackSelectionService

        """
        user_flags contain updated risk_factors from the most recent
        pregnancy welcome assessment. If this is passed, these risk
        factors will override whatever is on the user
        """
        if not user.is_member:
            log.info("user is not a member", user_id=user.id)
            return

        if not user.is_enterprise:
            log.info("user is not an enterprise member", user_id=user.id)
            return

        user_flags = user.current_risk_flags()

        log.info(
            "ca member matching - getting matches with 7 day availability",
            user_id=user.id,
        )
        logs_to_emit_with_matched_ca = []
        (cx_choices, available_advocate_ids_7days,) = cls.find_potential_care_advocates(
            user, user_flags, logs_to_emit_with_matched_ca=logs_to_emit_with_matched_ca
        )
        attempt_count = 1

        call_braze_async = bool_variation(
            "release-make-ca-braze-call-async",
            default=True,
        )

        if cx_choices:
            care_advocate_ids = [prac.practitioner_id for prac in cx_choices]
            log.info(
                "ca member matching - possible care advocate choices found for member",
                care_advocate_ids=care_advocate_ids,
                user_id=user.id,
            )

            active_tracks = user.active_tracks
            active_track_names = [track.name for track in active_tracks]
            track_svc = TrackSelectionService()
            is_eligible_for_intro = track_svc.any_eligible_for_intro_appointment(
                track_names=active_track_names
            )

            """
            For intro-eligible tracks, we will load balance based on utilization
            (number of appointments in the coming week/scheduled availability)

            For non-intro-eligible tracks, we will load balance based on recent assignments
            (number of assignments in the past two weeks)
            """
            if is_eligible_for_intro:
                log.info(
                    "ca member matching - using utilization ranking for load balancing",
                    user_id=user.id,
                    care_advocate_ids=care_advocate_ids,
                    user_track=user.current_member_track.name,
                )
                start_date = datetime.date.today()
                end_date = start_date + datetime.timedelta(days=6)
                selected_cx = cls.get_cx_with_lowest_weekly_utilization(
                    cx_choices, start_date, end_date, user.id
                )
            else:
                log.info(
                    "ca member matching - using recent assignment ranking for load balancing",
                    user_id=user.id,
                    user_track=user.current_member_track.name,
                    care_advocate_ids=care_advocate_ids,
                )
                end_date = datetime.date.today()
                start_date = end_date - datetime.timedelta(days=13)
                selected_cx = cls.get_cx_with_fewest_assignments_over_time_period(
                    cx_choices, start_date, end_date, user.id
                )

            try:
                cls.assign_selected_care_advocate(user, selected_cx, attempt_count)
                # We want to emit these saved logs together with some information about the eventual matched CA
                cls.log_with_matched_ca(
                    user=user,
                    user_flags=user_flags,
                    ca_id=selected_cx.practitioner_id,
                    logs_to_emit=logs_to_emit_with_matched_ca,
                )
            except IntegrityError as e:
                if "Duplicate entry" in str(e):
                    db.session.rollback()
                    log.error(
                        "Duplicate entry error. Care advocate is already assigned to member's care team",
                        user_id=user.id,
                        practitioner_id=selected_cx.practitioner_id,
                        practitioner_associations=user.practitioner_associations,
                    )
            return

        else:
            """
            As a last resort, we want to match a member to a CA instead of no one.
            We want to choose randomly from the pool of available advocates in the next 7 days.
            """
            pool_of_available_advocates_ids = available_advocate_ids_7days

            if len(pool_of_available_advocates_ids) > 0:
                log.info(
                    "ca member matching - choosing care advocate randomly from the pool of available advocates",
                    care_advocate_ids=pool_of_available_advocates_ids,
                    user_id=user.id,
                )

                selected_cx_practitioner_id = random.choice(
                    pool_of_available_advocates_ids
                )
                # TODO: Why are we not calling assign_selected_care_advocate here? Is it because we will mess up the metric that gets called over there?
                # Its funny that in the previous if statement we call assign_selected_care_advocate, which calls user.add_care_team_via_care_coordination,
                # but here we call user.add_care_team_via_care_coordination directly.
                # Probably the best thing to do is to get rid of assign_selected_care_advocate, or to call it here too (so we we get rid of the direct calls to user.add_care_team_via_care_coordination
                # And, ultimately, we can call update_care_advocate_attrs(user) inside assign_selected_care_advocate.
                # Anyhow, this whole flow might benefit from some refactoring.
                user.add_care_team_via_care_coordination(selected_cx_practitioner_id)
                if call_braze_async:
                    update_care_advocate_attrs.delay(user.id)
                else:
                    braze.update_care_advocate_attrs(user)

                ca_match_log = MemberMatchLog(
                    user_id=user.id,
                    care_advocate_id=selected_cx_practitioner_id,
                    country_code=user.country and user.country.alpha_2,
                    organization_id=user.organization.id if user.organization else None,
                    track=(
                        user.current_member_track.name
                        if user.current_member_track
                        else None
                    ),
                    user_flag_ids=",".join(str(flag.id) for flag in user_flags),
                    attempts=attempt_count,
                )
                db.session.add(ca_match_log)

                log.info(
                    "ca member matching - care advocate chosen for member",
                    care_advocate_id=selected_cx_practitioner_id,
                    user_id=user.id,
                    country=user.country and user.country.alpha_2,
                    organization=user.organization,
                    track=user.current_member_track.name,
                    user_flags=user_flags,
                )
                stats.increment(
                    metric_name="api.models.users.add_care_coordinator_for_member.random_assignment",
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                    tags=[f"practitioner_id:{selected_cx_practitioner_id}"],
                )
                # We want to emit these saved logs together with some information about the eventual matched CA
                cls.log_with_matched_ca(
                    user=user,
                    user_flags=user_flags,
                    ca_id=selected_cx_practitioner_id,
                    logs_to_emit=logs_to_emit_with_matched_ca,
                )

            else:
                """
                in the case that we still don't have a CA, we choose randomly from ALL CAs and alert the channel. this
                should always be handled by the previous step, but we never want a user to be without a CA.
                """
                stats.increment(
                    metric_name="api.models.users.add_care_coordinator_for_member.no_match",
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                )

                log.warning(
                    "ca member matching - did not find match",
                    user_id=user.id,
                    country=user.country and user.country.alpha_2,
                    organization=user.organization,
                    track=user.current_member_track.name,
                    user_flags=user_flags,
                )

                log.warning(
                    "ca member matching - assigning random CA that does not meet availability and capacity rules",
                    user_id=user.id,
                )
                all_advocates = db.session.query(AssignableAdvocate).all()
                advocate_ids = [
                    a.practitioner_id
                    for a in all_advocates
                    if a.admin_vacation != "on vacation forever"
                ]
                if not advocate_ids:
                    log.warning(
                        "ca member matching - failed to find match for member",
                        user_id=user.id,
                        country=user.country and user.country.alpha_2,
                        organization=user.organization,
                        track=user.current_member_track.name,
                        user_flags=user_flags,
                    )
                    return

                random_ca_id = random.choice(advocate_ids)
                user.add_care_team_via_care_coordination(random_ca_id)

                # We want to emit these saved logs together with some information about the eventual matched CA
                cls.log_with_matched_ca(
                    user=user,
                    user_flags=user_flags,
                    ca_id=random_ca_id,
                    logs_to_emit=logs_to_emit_with_matched_ca,
                )

                if call_braze_async:
                    update_care_advocate_attrs.delay(user.id)
                else:
                    braze.update_care_advocate_attrs(user)
                return

    @classmethod
    @tracer.wrap()
    def assign_selected_care_advocate(cls, user, selected_cx, attempt_count=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # import here to avoid circular import
        from tasks.braze import update_care_advocate_attrs

        user.add_care_team_via_care_coordination(selected_cx.practitioner_id)
        if bool_variation(
            "release-make-ca-braze-call-async",
            default=True,
        ):
            update_care_advocate_attrs.delay(user.id)
        else:
            braze.update_care_advocate_attrs(user)

        if bool_variation(
            "experiment-ca-validate-availability",
            default=False,
        ):
            cls.validate_consistent_next_availability(selected_cx.practitioner_id)

        log.info(
            "ca member matching - care advocate chosen for member",
            care_advocate_id=selected_cx.practitioner_id,
            user_id=user.id,
            country=user.country and user.country.alpha_2,
            organization=user.organization,
            track=user.current_member_track.name if user.current_member_track else None,
            user_flags=user.current_risk_flags(),
        )
        # TODO: Is this metric even used anywhere?
        stats.increment(
            metric_name="api.models.users.add_care_coordinator_for_member.matching_rule_set_assignment",
            pod_name=stats.PodNames.CARE_DISCOVERY,
            tags=[
                f"practitioner_id:{selected_cx.practitioner_id}",
                f"track:{user.current_member_track.name if user.current_member_track else None}",
            ],
        )

        ca_match_log = MemberMatchLog(
            user_id=user.id,
            care_advocate_id=selected_cx.practitioner_id,
            country_code=user.country and user.country.alpha_2,
            organization_id=user.organization.id if user.organization else None,
            track=(
                user.current_member_track.name if user.current_member_track else None
            ),
            user_flag_ids=",".join(str(flag.id) for flag in user.current_risk_flags()),
            attempts=attempt_count,
        )
        db.session.add(ca_match_log)

    @classmethod
    @tracer.wrap()
    def find_potential_care_advocates(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cls,
        user: User,
        user_flags: Iterable[RiskFlag],
        filter_by_language: Optional[str] = None,
        availability_before: datetime.datetime | None = None,
        logs_to_emit_with_matched_ca: list[str] | None = None,
    ):
        """
        Find potential care advocates for a given member

        @param filter_by_language: the iso-369-3/alpha-3 code for a language to filter
                                   practitioners by, or none
        @param availability_before: the cutoff we are looking for availability before. if not present,
        defaults to 7 days from now (the default also induces a weird starting window going back to start-of-today
        ET for unknown legacy reasons).
        @param logs_to_emit_with_matched_ca: an optional param that can be passed in to collect
        logs for later emission, so that our alerts can append information about the CA
        who is eventually matched to this user at the end of the process.
        """

        if logs_to_emit_with_matched_ca is None:
            # in this case these strings will just get dropped, but this
            # reduces the code complexity later on
            logs_to_emit_with_matched_ca = []

        log.info(
            "ca member matching - attempting to find matches with capacity within 7 days",
            user_id=user.id,
        )

        if availability_before:
            available_advocate_ids = cls.get_advocates_with_next_availability_before(
                availability_before=availability_before, user=user
            )
        else:
            available_advocate_ids = cls.get_advocates_with_capacity_and_availability(
                days_out_from_today=7,
                user=user,
            )

        if filter_by_language:
            log.info(
                "ca member matching - starting to filter by language",
                user_id=user.id,
                language=filter_by_language,
                pre_filter_ids=available_advocate_ids,
            )
            practitioner_language_ids = (
                db.session.query(practitioner_languages.c.user_id)
                .join(Language)
                .filter(
                    practitioner_languages.c.user_id.in_(available_advocate_ids),
                    Language.iso_639_3 == filter_by_language,
                )
                .all()
            )
            available_advocate_ids = [i[0] for i in practitioner_language_ids]

        cx_choices = cls.get_cx_choices_from_member_matching(
            available_advocate_ids,
            user=user,
            risk_factors=user_flags,
            logs_to_emit_with_matched_ca=logs_to_emit_with_matched_ca,
        )

        if not cx_choices:
            log.info(
                "ca member matching - attempting to find matches among catch all CAs",
                user_id=user.id,
                track=user.current_member_track.name,
                country=user.country and user.country.alpha_2,
                organization=user.organization and user.organization.name,
                language=filter_by_language,
            )
            logs_to_emit_with_matched_ca.append(
                "ca member matching - attempting to find matches among catch all CAs"
            )
            stats.increment(
                metric_name="api.models.users.add_care_coordinator_for_member.attempting_7_day_catch_all_CAs",
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )

            cx_choices = cls.get_catch_all_cx_choices_from_member_matching(
                available_advocate_ids,
                user=user,
                risk_factors=user_flags,
            )

        return cx_choices, available_advocate_ids

    @classmethod
    @tracer.wrap()
    def get_cx_choices_from_member_matching(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls,
        available_advocate_ids: List,
        user: "User",
        risk_factors=None,
        logs_to_emit_with_matched_ca: List[str] | None = None,
    ):
        """logs_to_emit_with_matched_ca is an optional param that can be passed in to collect
        logs for later emission, so that our alerts can append information about the CA
        who is eventually matched to this user at the end of the process."""
        from care_advocates.models.matching_rules import MatchingRuleSet  # noqa: F811

        return MatchingRuleSet.find_matches_for(
            user=user,
            available_advocate_ids=available_advocate_ids,
            risk_factors=risk_factors,
            logs_to_emit_with_matched_ca=logs_to_emit_with_matched_ca,
        )

    @classmethod
    @tracer.wrap()
    def get_catch_all_cx_choices_from_member_matching(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls, available_advocate_ids: List, user: "User", risk_factors=None
    ):
        from care_advocates.models.matching_rules import MatchingRuleSet  # noqa: F811

        return MatchingRuleSet.find_matches_for_catch_all(
            user=user,
            available_advocate_ids=available_advocate_ids,
            risk_factors=risk_factors,
        )

    @classmethod
    @tracer.wrap()
    def get_advocates_with_capacity_and_availability(
        cls, days_out_from_today: int, user: "User"
    ) -> List[int]:
        # relying on next_availability guarantees capacity and next_availability
        available_advocate_ids = cls.get_advocates_with_next_availability(
            days_out_from_today=days_out_from_today, user=user
        )
        return available_advocate_ids

    @classmethod
    @tracer.wrap()
    def validate_consistent_next_availability(cls, advocate_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Available advocates' next_availability should be on a day where they have capacity.
        We will log an error if that's not the case.
        """

        prac_next_availability, prac_daily_intro_capacity, prac_tz_str = (
            db.session.query(
                PractitionerProfile.next_availability,
                AssignableAdvocate.daily_intro_capacity,
                User.timezone,
            )
            .join(
                PractitionerProfile,
                PractitionerProfile.user_id == AssignableAdvocate.practitioner_id,
            )
            .join(
                User,
                PractitionerProfile.user_id == User.id,
            )
            .filter(PractitionerProfile.user_id == advocate_id)
            .one_or_none()
        )
        prac_tz = timezone(prac_tz_str)

        if prac_next_availability is None:
            # Log monitored by: https://app.datadoghq.com/monitors/125769175
            log.warn(
                "ca member matching - advocate has next_availability None",
                user_id=advocate_id,
                next_availability=None,
            )
            return

        today = datetime.datetime.utcnow()
        if prac_next_availability > today + datetime.timedelta(days=7):
            # Log monitored by: https://app.datadoghq.com/monitors/125769077
            log.warn(
                "ca member matching - advocate has next_availability in more than 7 days",
                user_id=advocate_id,
                next_availability=prac_next_availability.strftime("%Y-%m-%d %H:%M:%S"),
                today=today,
            )
            return

        # Confirm that practitioner has daily_intro_capacity on their next_availability date
        # capacity is based on practitioner's local timezone
        n_of_intro_appointments = (
            Appointment.intro_appointments_from_date_range_with_tz(
                practitioner_id=advocate_id,
                start_datetime=prac_next_availability,
                end_datetime=prac_next_availability,
                tz=prac_tz,
            )
            .with_entities(func.count())
            .one()[0]
        )

        if prac_daily_intro_capacity <= n_of_intro_appointments:
            # Log monitored by https://app.datadoghq.com/monitors/120157565
            log.warn(
                "ca member matching - advocate has no daily_intro_capacity remaining on next_availability date",
                user_id=advocate_id,
                next_availability=prac_next_availability.strftime("%Y-%m-%d %H:%M:%S"),
                daily_intro_capacity=prac_daily_intro_capacity,
                number_of_intro_appointments=n_of_intro_appointments,
            )
        else:
            log.info(
                "ca member matching - advocate has daily_intro_capacity remaining on next_availability date",
                user_id=advocate_id,
                next_availability=prac_next_availability.strftime("%Y-%m-%d %H:%M:%S"),
                daily_intro_capacity=prac_daily_intro_capacity,
                number_of_intro_appointments=n_of_intro_appointments,
            )

    @classmethod
    @tracer.wrap()
    def care_advocate_has_3_day_availability(cls, care_advocate_ids: List[int]) -> bool:
        # CA's are currently all scheduled in ET. We'll use ET here as well to be consistent with their schedules
        # and daily_intro_capacity
        now = datetime.datetime.utcnow().astimezone(timezone("America/New_York"))
        end = now + datetime.timedelta(days=3)

        three_days_from_now = end.replace(
            hour=23, minute=59, second=59, microsecond=999999
        ).astimezone(timezone("UTC"))

        care_advocate_with_3_day_availability = (
            db.session.query(PractitionerProfile.user_id)
            .filter(PractitionerProfile.user_id.in_(care_advocate_ids))
            .filter(PractitionerProfile.next_availability <= three_days_from_now)
        ).first()

        return True if care_advocate_with_3_day_availability else False

    @classmethod
    @tracer.wrap()
    def get_advocates_with_next_availability(
        cls, days_out_from_today: int, user: "User"
    ) -> List[int]:
        now = datetime.datetime.utcnow().astimezone(
            timezone("America/New_York")
        )  # same as capacity check -- get_available_advocates_with_max_capacity_query()
        end = now + datetime.timedelta(days=days_out_from_today)

        start_of_range = now.replace(minute=0, second=0, microsecond=0).astimezone(
            timezone("UTC")
        )
        end_of_range = end.replace(
            hour=23, minute=59, second=59, microsecond=999999
        ).astimezone(timezone("UTC"))

        advocates = (
            db.session.query(AssignableAdvocate)
            .join(
                PractitionerProfile,
                PractitionerProfile.user_id == AssignableAdvocate.practitioner_id,
            )
            .filter(PractitionerProfile.next_availability >= start_of_range)
            .filter(PractitionerProfile.next_availability <= end_of_range)
        ).all()

        advocate_ids = [a.practitioner_id for a in advocates]

        log.info(
            "ca member matching - found advocates with availability",
            care_advocate_ids=advocate_ids,
            user_id=user.id,
            days_out=days_out_from_today,
            start_of_range=str(start_of_range),
            end_of_range=str(end_of_range),
        )
        return advocate_ids

    @classmethod
    @tracer.wrap()
    def get_advocates_with_next_availability_before(
        cls, availability_before: datetime.datetime, user: "User"
    ) -> List[int]:
        now = datetime.datetime.utcnow()

        advocates = (
            db.session.query(AssignableAdvocate)
            .join(
                PractitionerProfile,
                PractitionerProfile.user_id == AssignableAdvocate.practitioner_id,
            )
            .filter(PractitionerProfile.next_availability >= now)
            .filter(PractitionerProfile.next_availability <= availability_before)
        ).all()

        advocate_ids = [a.practitioner_id for a in advocates]

        log.info(
            "ca member matching - found advocates with availability before end-date",
            care_advocate_ids=advocate_ids,
            user_id=user.id,
            start_of_range=str(now),
            end_of_range=str(availability_before),
        )
        return advocate_ids

    @classmethod
    @tracer.wrap()
    def get_advocates_with_capacity(
        cls, days_out_from_today: int, user: "User"
    ) -> List[int]:
        return cls.get_advocates_with_daily_intro_capacity(
            days_out_from_today=days_out_from_today, user=user
        )

    @classmethod
    @tracer.wrap()
    def get_advocates_with_max_capacity(
        cls, days_out_from_today: int, user: "User"
    ) -> List[int]:
        q = cls.get_advocates_with_max_capacity_query(days_out_from_today, user)

        available_advocate_ids = cls.get_advocate_ids(q)

        log.info(
            "ca member matching - All available advocates not on vacation and are not at max capacity",
            user_id=user.id,
            in_advocate_ids=available_advocate_ids,
            days_out=days_out_from_today,
        )

        return available_advocate_ids

    @classmethod
    @tracer.wrap()
    def get_advocates_with_daily_intro_capacity(
        cls, days_out_from_today: int, user: "User"
    ) -> List[int]:
        q = cls.get_advocates_with_daily_intro_capacity_query(days_out_from_today, user)

        available_advocate_ids = cls.get_advocate_ids(q)

        log.info(
            "ca member matching - All available advocates not on vacation and are not at daily intro capacity",
            user_id=user.id,
            in_advocate_ids=available_advocate_ids,
            days_out=days_out_from_today,
        )

        return available_advocate_ids

    @classmethod
    @tracer.wrap()
    def get_advocates_with_max_capacity_query(
        cls, days_out_from_today: int, user: "User"
    ) -> Query:
        today = datetime.datetime.utcnow()  # current UTC date and time
        q = cls.get_advocates_not_on_vacation(user, date=today)

        if user:
            log.info(
                "ca member matching - All available advocates not on vacation.",
                user_id=user.id,
                in_advocate_ids=cls.get_advocate_ids(q),
                days_out=days_out_from_today,
            )

        # Care Advocates are all scheduled in New York time (for now). If a CA has an appointment
        # booked for after 8pm Eastern that appointment is being bumped in tomorrow's capacity. We
        # look for appointments in New York time which keeps max capacity within the New York day.
        # This is different to how bookings check for max capacity, which is done in the practitioner's timezone
        today_eastern = today.astimezone(timezone("America/New_York"))

        # create the initial conditions
        conditions = [
            (
                AssignableAdvocate.max_capacity
                > Appointment.number_of_appointments_on_date(
                    AssignableAdvocate.practitioner_id, today_eastern
                )
            )
        ]

        # commenting this out for now. it's very slow and we don't use this data often
        # if there is a demand for the data that comes up, we'll make this logging function asynchronous
        """
        if user:
            cls.log_advocates_not_on_vacation_at_max_capacity(
                q, user, today_eastern, days_out_from_today
            )
        """

        for i in range(1, days_out_from_today):
            date = today_eastern + datetime.timedelta(days=i)
            conditions.append(
                (
                    AssignableAdvocate.max_capacity
                    > Appointment.number_of_appointments_on_date(
                        AssignableAdvocate.practitioner_id, date
                    )
                )
            )  # add conditions related to practitioner availability

            # commenting this out for now. it's very slow and we don't use this data often
            # if there is a demand for the data that comes up, we'll make this logging function asynchronous
            """
            # logging the conditions - happens each iteration of the loop
            if user:
                cls.log_advocates_not_on_vacation_at_max_capacity(
                    q, user, date, days_out_from_today
                )
            """
        q = q.filter(or_(*conditions))  # add the conditions to the query

        return q

    @classmethod
    @tracer.wrap()
    def get_advocates_with_daily_intro_capacity_query(
        cls, days_out_from_today: int, user: "User"
    ) -> Query:
        today = datetime.datetime.utcnow()
        q = cls.get_advocates_not_on_vacation(user, date=today)

        if user:
            log.info(
                "ca member matching - All available advocates not on vacation.",
                user_id=user.id,
                in_advocate_ids=cls.get_advocate_ids(q),
                days_out=days_out_from_today,
            )

        # Care Advocates are all scheduled in New York time (for now). If a CA has an appointment
        # booked for after 8pm Eastern that appointment is being bumped in tomorrow's capacity. We
        # look for appointments in New York time which keeps max capacity within the New York day.
        # This is different to how bookings check for max capacity, which is done in the practitioner's timezone
        today_eastern = today.astimezone(timezone("America/New_York"))

        # create the initial conditions
        conditions = [
            (
                AssignableAdvocate.daily_intro_capacity
                > Appointment.number_of_appointments_on_date(
                    AssignableAdvocate.practitioner_id, today_eastern
                )
            )
        ]

        for i in range(1, days_out_from_today):
            date = today_eastern + datetime.timedelta(days=i)
            conditions.append(
                (
                    AssignableAdvocate.daily_intro_capacity
                    > Appointment.number_of_appointments_on_date(
                        AssignableAdvocate.practitioner_id, date
                    )
                )
            )  # add conditions related to practitioner availability

        q = q.filter(or_(*conditions))  # add the conditions to the query

        return q

    @classmethod
    @tracer.wrap()
    def get_advocate_ids(cls, q: Query) -> List[int]:
        advocates = q.with_entities(AssignableAdvocate.practitioner_id).all()

        return [id for (id,) in advocates]

    @classmethod
    @tracer.wrap()
    def log_advocates_not_on_vacation_at_max_capacity(
        cls, q: Query, user: "User", date: datetime.datetime, days_out_from_today: int
    ) -> None:
        advocates_at_max = (
            AssignableAdvocate.max_capacity
            <= Appointment.number_of_appointments_on_date(
                AssignableAdvocate.practitioner_id, date
            )
        )
        all_advocates_at_max_capacity = q.filter(advocates_at_max).all()

        advocate_id_max_capacity = []
        for advocate in all_advocates_at_max_capacity:
            num_appts = PractitionerProfile.query.filter(
                Appointment.number_of_appointments_on_date(
                    advocate.practitioner_id, date
                )
            ).all()
            advocate_id_max_capacity.append(
                {
                    "id": advocate.practitioner_id,
                    "first_name": advocate.practitioner.user.first_name,
                    "max_capacity": advocate.max_capacity,
                    "number_of_appointments_on_date": len(num_appts),
                    "date": date.strftime("%m/%d/%Y, %H:%M:%S"),
                }
            )

        log.info(
            "ca member matching - All available advocates not on vacation and at max capacity on date",
            user_id=user.id,
            country=user.country and user.country.alpha_2,
            organization=user.organization,
            track=user.current_member_track.name,
            user_flags=user.current_risk_flags(),
            in_advocates=advocate_id_max_capacity,
            days_out=days_out_from_today,
            date=date,
        )

    @classmethod
    @tracer.wrap()
    def get_advocates_not_on_vacation(
        cls, user: "User", date: datetime.datetime = None  # type: ignore[assignment] # Incompatible default for argument "date" (default has type "None", argument has type "datetime")
    ) -> Query:
        if date is None:
            date = datetime.datetime.utcnow()

        if user:
            cls.log_advocates_on_vacation(user, date)

        return AssignableAdvocate.query.filter(
            or_(
                (
                    AssignableAdvocate.vacation_started_at.is_(None)
                    & AssignableAdvocate.vacation_ended_at.is_(None)
                ),
                AssignableAdvocate.vacation_ended_at < date,
                AssignableAdvocate.vacation_started_at > date,
            )
        )

    @classmethod
    @tracer.wrap()
    def get_advocates_on_vacation(
        cls, user: "User", date: datetime.datetime = None  # type: ignore[assignment] # Incompatible default for argument "date" (default has type "None", argument has type "datetime")
    ) -> Query:
        if date is None:
            date = datetime.datetime.utcnow()

        return AssignableAdvocate.query.filter(
            and_(
                AssignableAdvocate.vacation_started_at <= date,
                AssignableAdvocate.vacation_ended_at >= date,
            )
        )

    @classmethod
    @tracer.wrap()
    def log_advocates_on_vacation(cls, user: "User", date: datetime.datetime) -> None:
        all_advocates_on_vacation = cls.get_advocates_on_vacation(user, date).all()
        advocate_id_vacation = []
        for advocate in all_advocates_on_vacation:
            advocate_id_vacation.append(
                {
                    "id": advocate.practitioner_id,
                    "first_name": advocate.practitioner.user.first_name,
                    "vacation_started_at": advocate.vacation_started_at.strftime(
                        "%m/%d/%Y, %H:%M:%S"
                    ),
                    "vacation_ended_at": advocate.vacation_ended_at.strftime(
                        "%m/%d/%Y, %H:%M:%S"
                    ),
                }
            )

        log.info(
            "ca member matching - All advocates currently on vacation.",
            user_id=user.id,
            country=user.country and user.country.alpha_2,
            organization=user.organization,
            track=user.current_member_track.name,
            user_flags=user.current_risk_flags(),
            in_advocates=advocate_id_vacation,
            date=date,
        )

    @classmethod
    @tracer.wrap()
    def replace_care_coordinator_for_member(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not user.is_member:
            log.warning("User is not a member", user_id=user.id)
            return

        if cls.remove_care_advocate_from_member(user) is not None:
            db.session.flush()

        log.info("Add/Re-add care coordinators", user_id=user.id)
        cls.add_care_coordinator_for_member(user)

    @classmethod
    @tracer.wrap()
    def remove_care_advocate_from_member(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info("Checking for already assigned care coordinator", user_id=user.id)
        if not user.care_coordinators:
            log.info("User does not have care coordinators.", user_id=user.id)
            return None
        else:
            for mpa in user.practitioner_associations:
                if mpa.type == CareTeamTypes.CARE_COORDINATOR:
                    log.info(
                        "Removing care advocate from member",
                        user_id=user.id,
                        practitioner_id=mpa.practitioner_id,
                    )
                    # Additional temp comment for current issue
                    log.info(
                        "Deleting rows in MemberPractitionerAssociation",
                        user_id=user.id,
                        practitioner_id=mpa.practitioner_id,
                    )
                    user.practitioner_associations.remove(mpa)
                    return mpa.practitioner_id

    @classmethod
    @tracer.wrap()
    def get_cx_with_lowest_weekly_utilization(
        cls,
        cx_choices: List["AssignableAdvocate"],
        start_date: datetime.date,
        end_date: datetime.date,
        member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "member_id" (default has type "None", argument has type "int")
    ) -> "AssignableAdvocate":
        """
        # Weekly utilization = total appointments / total hours (7-day span starting with current day)
        # End_date is inclusive (through end of day)
        """
        if not cx_choices or not isinstance(cx_choices, list):
            log.error(
                "Missing or invalid cx_choices for weekly utilization",
                user_id=member_id,
                type=type(cx_choices),
            )
            return  # type: ignore[return-value] # Return value expected
        if len(cx_choices) == 1:
            log.info(
                "ca member matching - Only 1 care advocate found",
                cx_choices=cx_choices,
                user_id=member_id,
            )
            return cx_choices[0]

        # Turn into dictionary by prac_id
        cx_choices_dict = {cx.practitioner_id: cx for cx in cx_choices}
        cx_practitioner_ids = list(cx_choices_dict.keys())

        # Put datetimes into the times we need (begining and end of day)
        start_datetime = datetime.datetime.combine(
            start_date, datetime.time(0, 0, 0, 0)
        )
        end_datetime = datetime.datetime.combine(
            end_date, datetime.time(23, 59, 59, 999)
        )
        # Total appointments
        appts_per_prac, _ = MassAvailabilityCalculator.get_mass_existing_appointments(
            start_time=start_datetime,
            end_time=end_datetime,
            provider_ids=cx_practitioner_ids,
        )

        # Total schedule_event hours
        schedule_events = (
            MassAvailabilityCalculator.get_mass_existing_available_schedule_events(
                start_time=start_datetime,
                end_time=end_datetime,
                user_ids=cx_practitioner_ids,
            )
        )
        # No schedule events = no hours to calculate utilization
        if not schedule_events:
            log.error(
                "No schedule_events found to calculate weekly utilization",
                user_id=member_id,
                cx_practitioner_ids=cx_practitioner_ids,
                start_date=start_date,
                end_date=end_date,
            )
            return  # type: ignore[return-value] # Return value expected

        # Calculate weekly utilization per cx
        hours_per_prac = cls._total_schedule_event_hours_by_cx(schedule_events)
        sorted_utilizations = cls._weekly_utilization_by_cx_sorted(
            appts_per_prac, hours_per_prac
        )
        sorted_utilizations_log = [
            f"practitioner_id={util.user_id}: utilization={util.utilization}"
            for util in sorted_utilizations
        ]
        log.info(
            "ca member matching - Care advocate utilizations",
            user_id=member_id,
            utilizations=sorted_utilizations_log,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        # Cxs with lowest utilizations (could be multiples tied)
        lowest_cx_ids, lowest_utilization = cls._lowest_utilization_cx_ids(
            sorted_utilizations
        )
        log.info(
            "ca member matching - Care advocates with lowest utilization",
            user_id=member_id,
            cx_ids=lowest_cx_ids,
            utilization=lowest_utilization,
        )

        # Return random cx with lowest utilization (possibly just 1)
        selected_cx_id = random.choice(lowest_cx_ids)
        log.info(
            "ca member matching - Selected care advocate with lowest utilization",
            user_id=member_id,
            cx_id=selected_cx_id,
            utilization=lowest_utilization,
        )
        return cx_choices_dict[selected_cx_id]

    @classmethod
    @tracer.wrap()
    def get_cx_with_fewest_assignments_over_time_period(
        cls,
        cx_choices: List["AssignableAdvocate"],
        start_date: datetime.date,
        end_date: datetime.date,
        member_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "member_id" (default has type "None", argument has type "int")
    ) -> "AssignableAdvocate":
        """
        # End_date is inclusive (through end of day)
        """
        if not cx_choices or not isinstance(cx_choices, list):
            log.error(
                "Missing or invalid cx_choices for recent assignments",
                user_id=member_id,
                type=type(cx_choices),
            )
            return  # type: ignore[return-value] # Return value expected
        if len(cx_choices) == 1:
            log.info(
                "ca member matching - Only 1 care advocate found",
                cx_choices=cx_choices,
                user_id=member_id,
            )
            return cx_choices[0]

        # Turn into dictionary by prac_id
        cx_choices_dict = {cx.practitioner_id: cx for cx in cx_choices}
        cx_practitioner_ids = list(cx_choices_dict.keys())

        # Put datetimes into the times we need (beginning and end of day)
        start_datetime = datetime.datetime.combine(
            start_date, datetime.time(0, 0, 0, 0)
        )
        end_datetime = datetime.datetime.combine(
            end_date, datetime.time(23, 59, 59, 999)
        )

        sorted_number_of_assignments = (
            cls._number_of_assignments_in_time_range_by_cx_sorted(
                cx_practitioner_ids, start_datetime, end_datetime
            )
        )
        sorted_number_of_assignments_log = [
            f"practitioner_id={assignments.user_id}: number_of_assignments={assignments.assignment_count}"
            for assignments in sorted_number_of_assignments
        ]
        log.info(
            "ca member matching - Care advocate number of assignments",
            user_id=member_id,
            number_of_assignments=sorted_number_of_assignments_log,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        # Cxs with the fewest number of assignments (could be multiples tied)
        (
            lowest_cx_ids,
            lowest_number_of_assignments,
        ) = cls._lowest_number_of_assignments_cx_ids(sorted_number_of_assignments)
        log.info(
            "ca member matching - Care advocates with lowest number of assignments",
            user_id=member_id,
            cx_ids=lowest_cx_ids,
            number_of_assignments=lowest_number_of_assignments,
        )

        # Return random cx with the fewest number of assignments (possibly just 1)
        selected_cx_id = random.choice(lowest_cx_ids)
        log.info(
            "ca member matching - Selected care advocate with lowest number of assignments",
            user_id=member_id,
            cx_id=selected_cx_id,
            number_of_assignments=lowest_number_of_assignments,
        )
        return cx_choices_dict[selected_cx_id]

    @tracer.wrap()
    def _total_schedule_event_hours_by_cx(
        schedule_events: Dict[int, list]
    ) -> Dict[int, float]:
        hours_per_prac = defaultdict(float)
        if schedule_events:
            for _, prac_events in schedule_events.items():
                for event in prac_events:
                    prac_id = str(event.schedule.user_id)
                    seconds = (event.ends_at - event.starts_at).total_seconds()
                    hours = seconds / 60 / 60
                    hours_per_prac[prac_id] = hours_per_prac[prac_id] + hours
        return hours_per_prac  # type: ignore[return-value] # Incompatible return value type (got "defaultdict[str, Any]", expected "Dict[int, float]")

    @tracer.wrap()
    def _weekly_utilization_by_cx_sorted(
        appts_per_prac: Dict[int, list],
        hours_per_prac: Dict[int, float],
    ) -> List[NamedTuple]:
        # Use namedtuple for sorting with keys intead of the default number indexes
        Utilization = namedtuple("Utilization", "user_id utilization")
        weekly_utilizations = []
        for user_id, hours in hours_per_prac.items():
            if hours > 0:
                num_appts = len(appts_per_prac[int(user_id)])
                utilization = round((num_appts / hours), 3)
                weekly_utilizations.append(
                    Utilization(user_id=int(user_id), utilization=float(utilization))
                )
        return sorted(weekly_utilizations, key=attrgetter("utilization"))

    @tracer.wrap()
    def _lowest_utilization_cx_ids(
        sorted_utilizations: List[NamedTuple],
    ) -> Tuple[List[int], float]:
        # First record is always the lowest, but more could exist
        lowest_cx_ids = [sorted_utilizations[0].user_id]  # type: ignore[attr-defined] # "NamedTuple" has no attribute "user_id"
        lowest_utilization = sorted_utilizations[0].utilization  # type: ignore[attr-defined] # "NamedTuple" has no attribute "utilization"
        for i in range(1, len(sorted_utilizations)):
            if sorted_utilizations[i].utilization == lowest_utilization:  # type: ignore[attr-defined] # "NamedTuple" has no attribute "utilization"
                lowest_cx_ids.append(sorted_utilizations[i].user_id)  # type: ignore[attr-defined] # "NamedTuple" has no attribute "user_id"
            else:
                # No need to keep looking
                break
        return lowest_cx_ids, lowest_utilization

    @tracer.wrap()
    def _number_of_assignments_in_time_range_by_cx_sorted(
        cx_practitioner_ids: List[int],
        start_datetime: DateTime,
        end_datetime: DateTime,
    ) -> List[NamedTuple]:

        # get all assignments for ca's with assignments
        mpa_subquery = (
            db.session.query(
                MemberPractitionerAssociation.practitioner_id,
                func.count(MemberPractitionerAssociation.practitioner_id).label(
                    "assignment_count"
                ),
            )
            .filter(
                MemberPractitionerAssociation.practitioner_id.in_(cx_practitioner_ids),
                MemberPractitionerAssociation.type == CareTeamTypes.CARE_COORDINATOR,
                MemberPractitionerAssociation.created_at >= start_datetime,
                MemberPractitionerAssociation.created_at <= end_datetime,
            )
            .group_by(MemberPractitionerAssociation.practitioner_id)
            .subquery()
        )

        # make sure to include ca's with zero assignments
        assignments_per_prac = (
            db.session.query(
                PractitionerProfile.user_id,
                db.case(
                    [
                        (mpa_subquery.c.assignment_count.is_(None), 0),
                    ],
                    else_=mpa_subquery.c.assignment_count,
                ).label("assignment_count"),
            )
            .filter(
                PractitionerProfile.user_id.in_(cx_practitioner_ids),
            )
            .outerjoin(
                mpa_subquery,
                PractitionerProfile.user_id == mpa_subquery.c.practitioner_id,
            )
            .order_by(mpa_subquery.c.assignment_count)
            .options(Load(PractitionerProfile).load_only(PractitionerProfile.user_id))  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
            .all()
        )
        return assignments_per_prac

    @tracer.wrap()
    def _lowest_number_of_assignments_cx_ids(
        sorted_number_of_assignments: List[Tuple],
    ) -> Tuple[List[int], float]:
        # First record is always the lowest, but more could exist
        lowest_cx_ids = [sorted_number_of_assignments[0].user_id]  # type: ignore[attr-defined] # "Tuple[Any, ...]" has no attribute "user_id"
        lowest_sorted_number_of_assignments = sorted_number_of_assignments[  # type: ignore[attr-defined] # "Tuple[Any, ...]" has no attribute "assignment_count"
            0
        ].assignment_count
        for i in range(1, len(sorted_number_of_assignments)):
            if (
                sorted_number_of_assignments[i].assignment_count  # type: ignore[attr-defined] # "Tuple[Any, ...]" has no attribute "assignment_count"
                == lowest_sorted_number_of_assignments
            ):
                lowest_cx_ids.append(sorted_number_of_assignments[i].user_id)  # type: ignore[attr-defined] # "Tuple[Any, ...]" has no attribute "user_id"
            else:
                # No need to keep looking
                break
        return lowest_cx_ids, lowest_sorted_number_of_assignments


@tracer.wrap()
def sort_and_merge_dates(dates: List[TimeRange]) -> List[TimeRange]:
    if not dates:
        return []

    sorted_merged_dates = []
    sorted_dates = sorted(dates, key=lambda datetime: datetime.start_time)  # type: ignore[arg-type,return-value] # Argument "key" to "sorted" has incompatible type "Callable[[TimeRange], Optional[datetime]]"; expected "Callable[[TimeRange], Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]]" #type: ignore[return-value] # Incompatible return value type (got "Optional[datetime]", expected "Union[SupportsDunderLT[Any], SupportsDunderGT[Any]]")

    current_start_date = sorted_dates[0].start_time
    current_end_date = sorted_dates[0].end_time
    for date in sorted_dates:
        if current_end_date < date.end_time:
            if current_end_date >= date.start_time:
                current_end_date = date.end_time
            else:
                sorted_merged_dates.append(
                    TimeRange(start_time=current_start_date, end_time=current_end_date)
                )
                current_start_date = date.start_time
                current_end_date = date.end_time

    sorted_merged_dates.append(
        TimeRange(start_time=current_start_date, end_time=current_end_date)
    )

    return sorted_merged_dates
