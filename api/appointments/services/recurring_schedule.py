from __future__ import annotations

import datetime
from typing import Tuple

import ddtrace
from dateutil import rrule, tz
from flask_restful import abort
from sqlalchemy.orm.scoping import ScopedSession

from appointments.models.constants import ScheduleStates
from appointments.models.provider_schedules import ProviderScheduleRecurringBlock
from appointments.models.schedule import Schedule
from appointments.models.schedule_event import ScheduleEvent
from appointments.repository.schedules import (
    ScheduleEventRepository,
    ScheduleRecurringBlockRepository,
)
from appointments.services.schedule import detect_schedule_conflict
from appointments.utils.recurring_availability_utils import (
    check_conflicts_between_two_event_series,
)
from common.models.scheduled_maintenance import ScheduledMaintenance
from storage.connection import db
from utils.log import logger

log = logger(__name__)
RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_DAYS = 90


class RecurringScheduleAvailabilityService:
    def __init__(
        self,
        session: ScopedSession | None = None,
        schedule_recurring_block_repo: ScheduleRecurringBlockRepository | None = None,
        schedule_event_repo: ScheduleEventRepository | None = None,
    ):
        self.session = session or db.session
        self.schedule_recurring_block_repo = (
            schedule_recurring_block_repo
            or ScheduleRecurringBlockRepository(session=self.session)
        )
        self.schedule_event_repo = schedule_event_repo or ScheduleEventRepository(
            session=self.session
        )

    def get_schedule_recurring_block_by_user_and_date_range(
        self, user_id: int, starts_at: datetime.datetime, until: datetime.datetime
    ) -> list[ProviderScheduleRecurringBlock]:
        return self.schedule_recurring_block_repo.get_schedule_recurring_blocks(
            user_id=user_id, starts_at=starts_at, until=until
        )

    def get_exact_schedule_recurring_block_by_user_and_date_range(
        self,
        user_id: int,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        until: datetime.datetime,
    ) -> ProviderScheduleRecurringBlock | None:
        return self.schedule_recurring_block_repo.get_schedule_recurring_block(
            user_id=user_id, starts_at=starts_at, ends_at=ends_at, until=until
        )

    def get_schedule_recurring_block_by_id(
        self,
        schedule_recurring_block_id: int,
    ) -> ProviderScheduleRecurringBlock | None:
        return self.schedule_recurring_block_repo.get_schedule_recurring_block_by_id(
            schedule_recurring_block_id=schedule_recurring_block_id
        )

    def get_schedule_recurring_block_by_schedule_event(
        self,
        schedule_event_id: int,
    ) -> list[ProviderScheduleRecurringBlock]:
        return self.schedule_recurring_block_repo.get_schedule_recurring_block_by_schedule_event(
            schedule_event_id=schedule_event_id
        )

    def detect_booked_appointments_in_block(
        self,
        schedule_recurring_block_id: int,
        user_id: int,
    ) -> None:
        """
        Checks for the presence of any booked appointment
        during the block
        """
        recurring_block = self.get_schedule_recurring_block_by_id(
            schedule_recurring_block_id=schedule_recurring_block_id,
        )

        if recurring_block and recurring_block.schedule_events:
            for event in recurring_block.schedule_events:
                count_existing_appointments = self._get_count_existing_appointments_in_schedule_recurring_block(
                    user_id=user_id,
                    starts_at=event.starts_at,  # type: ignore[arg-type] # Argument "starts_at" to "_get_count_existing_appointments_in_schedule_recurring_block" of "RecurringScheduleAvailabilityService" has incompatible type "Union[datetime, None, Any]"; expected "datetime"
                    ends_at=event.ends_at,  # type: ignore[arg-type] # Argument "ends_at" to "_get_count_existing_appointments_in_schedule_recurring_block" of "RecurringScheduleAvailabilityService" has incompatible type "Union[datetime, None, Any]"; expected "datetime"
                )

                if count_existing_appointments:
                    log.debug(f"Not deleting {event} - existing booking!")
                    abort(400, message="Cannot delete when you are booked!")
        else:
            abort(404, message="Schedule recurring block not found")

    def _get_count_existing_appointments_in_schedule_recurring_block(
        self,
        user_id: int,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
    ) -> int:
        return self.schedule_recurring_block_repo.get_count_existing_appointments_in_schedule_recurring_block(
            user_id=user_id,
            starts_at=starts_at,
            ends_at=ends_at,
        )

    def detect_schedule_recurring_block_conflict(
        self,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        starts_range: datetime.datetime,
        until_range: datetime.datetime,
        week_days_index: list[int],
        frequency: str,
        member_timezone: str,
        schedule_id: int,
    ) -> None:
        """
        Checks for availability conflicts given the requested new availability blocks
        """
        with ddtrace.tracer.trace(name=f"{__name__}.db_query_get_schedule"):
            schedule = db.session.query(Schedule).get(schedule_id)

        query_end_time = starts_at + datetime.timedelta(
            days=RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_DAYS
        )

        with ddtrace.tracer.trace(
            name=f"{__name__}.db_query_get_existing_schedule_events"
        ):
            existing = (
                schedule.existing_events(starts_at, query_end_time)
                .filter(ScheduleEvent.state == ScheduleStates.available)
                .all()
            )

        existing_availability = [(x.starts_at, x.ends_at) for x in existing]

        new_recurring_blocks = self._occurrences(
            starts_at=starts_at,
            ends_at=ends_at,
            start_range=starts_range,
            until_range=until_range,
            week_days_index=week_days_index,
            frequency=frequency,
            member_timezone=member_timezone,
        )

        with ddtrace.tracer.trace(name=f"{__name__}.check_schedule_conflict"):
            schedule_conflict_exists = check_conflicts_between_two_event_series(
                existing_availability, new_recurring_blocks
            )

        if schedule_conflict_exists:
            log.error(f"Conflicts with {existing}")
            abort(400, message="Conflict with existing availability!")

        # check with maintenance schedule, forked from
        # https://gitlab.com/maven-clinic/maven/maven/-/blob/main/api/appointments/services/schedule.py?ref_type=heads#L188-198
        overlapped_maintenance = (
            db.session.query(ScheduledMaintenance)
            .filter(
                (ScheduledMaintenance.scheduled_start <= query_end_time)
                & (starts_at <= ScheduledMaintenance.scheduled_end)
            )
            .all()
        )

        overlapped_maintenance_intervals = [
            (x.scheduled_start, x.scheduled_end) for x in overlapped_maintenance
        ]
        maintenance_overlap_exists = check_conflicts_between_two_event_series(
            overlapped_maintenance_intervals, new_recurring_blocks
        )

        if maintenance_overlap_exists:
            abort(400, message="Conflict with existing maintenance window!")

    def create_schedule_recurring_block(
        self,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        frequency: str,
        until: datetime.datetime,
        schedule_id: int,
        week_days_index: list[int],
        member_timezone: str,
        user_id: int,
    ) -> int | None:
        """
        week_days_index corresponds to the ordinal weekdays.
        So 0 == Monday and 6==Sunday.

        Will not recreate schedule events again for dates before
        the latest_date_events_created
        """
        existing_block = self.get_exact_schedule_recurring_block_by_user_and_date_range(
            user_id=user_id,
            starts_at=starts_at,
            ends_at=ends_at,
            until=until,
        )

        if existing_block:
            # if a block exists, look at the time the last successfully created event ended
            starts_range = existing_block.latest_date_events_created
            block_id = existing_block.id
        else:
            recurring_block = self.schedule_recurring_block_repo.create(
                starts_at=starts_at,
                ends_at=ends_at,
                frequency=frequency,
                until=until,
                schedule_id=schedule_id,
                week_days_index=week_days_index,
            )
            starts_range = starts_at
            block_id = recurring_block.id
        schedule = db.session.query(Schedule).get(schedule_id)
        for start_dt, end_dt in self._occurrences(
            starts_at=starts_at,
            ends_at=ends_at,
            start_range=starts_range,  # type: ignore[arg-type] # Argument "start_range" to "_occurrences" of "RecurringScheduleAvailabilityService" has incompatible type "Optional[datetime]"; expected "datetime"
            until_range=until,
            week_days_index=week_days_index,
            frequency=frequency,
            member_timezone=member_timezone,
        ):
            # check this again in case there was a delay running the job and a conflict was created
            detect_schedule_conflict(schedule, start_dt, end_dt)
            self.schedule_event_repo.create(
                starts_at=start_dt,
                ends_at=end_dt,
                schedule_recurring_block_id=block_id,
            )
            log.info(
                "Creating individual availability as part of recurring availability",
                schedule_id=schedule_id,
                starts_at=starts_at,
                until=until,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            self.schedule_recurring_block_repo.update_latest_date_events_created(
                schedule_recurring_block_id=block_id,
                date=end_dt,
            )
        return block_id

    @staticmethod
    def _create_rrule(
        starts_at: datetime.datetime,
        week_days_index: list[int],
        until: datetime.datetime,
        frequency: str,
    ) -> rrule.rrule:
        """
        Create rrule to generate recurring instances based on rules

        Our current use case only includes daily and weekly.
        Further implementation TODO if we want to implement monthly frequency.
        """
        utc_tz = tz.gettz("UTC")
        if isinstance(until, datetime.date):
            until = datetime.datetime.combine(
                until, datetime.time(hour=23, minute=59, second=59, tzinfo=utc_tz)
            )
        else:
            until = until.replace(hour=23, minute=59, second=59, tzinfo=utc_tz)

        _kwargs = {
            "dtstart": starts_at,
            "until": until,
        }

        if week_days_index:
            _kwargs["byweekday"] = tuple(week_days_index)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[int, ...]", target has type "datetime")

        #  for our purposes can be currently daily or weekly
        freq = getattr(rrule, frequency)

        log.info(f"rrule: {freq}, {_kwargs}")
        return rrule.rrule(freq, **_kwargs)  # type: ignore[arg-type] # Argument 2 to "rrule" has incompatible type "**Dict[str, datetime]"; expected "int" #type: ignore[arg-type] # Argument 2 to "rrule" has incompatible type "**Dict[str, datetime]"; expected "Union[weekday, int, None]" #type: ignore[arg-type] # Argument 2 to "rrule" has incompatible type "**Dict[str, datetime]"; expected "Optional[int]" #type: ignore[arg-type] # Argument 2 to "rrule" has incompatible type "**Dict[str, datetime]"; expected "Union[int, Iterable[int], None]" #type: ignore[arg-type] # Argument 2 to "rrule" has incompatible type "**Dict[str, datetime]"; expected "Union[int, weekday, Iterable[int], Iterable[weekday], None]" #type: ignore[arg-type] # Argument 2 to "rrule" has incompatible type "**Dict[str, datetime]"; expected "bool"

    def _occurrences(
        self,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        start_range: datetime.datetime,
        until_range: datetime.datetime,
        week_days_index: list[int],
        frequency: str,
        member_timezone: str,
    ) -> list[Tuple[datetime.datetime, datetime.datetime]]:
        """
        Convert utc sent datetimes to timezone aware datetimes
        so rrule can take into account daylight savings.

        Convert back to utc to save in database.

        starts_at and ends_at are used to calculate duration

        start_range and until_range handle the datetime range
        of the rrule which can be different from starts_at and
        ends_at if the schedule event creation is not happening
        for the first time
        """
        occurrences = []

        utc_tz = tz.gettz("UTC")
        local_starts_range = self._convert_datetime_to_tz(start_range, member_timezone)
        local_until_range = self._convert_datetime_to_tz(until_range, member_timezone)
        utc_until = until_range.replace(tzinfo=utc_tz)

        rule = self._create_rrule(
            local_starts_range, week_days_index, utc_until, frequency
        )

        # duration needs to be based on the utc times sent in or else we risk the wrong duration
        # when crossing dst boundaries
        duration = (ends_at - starts_at).total_seconds()
        for start in rule.between(local_starts_range, local_until_range, inc=True):
            ends = start + datetime.timedelta(seconds=duration)
            # Convert start and end back to UTC before appending, but remove utc offset in timestamp for comparisons
            occurrences.append(
                (
                    start.astimezone(utc_tz).replace(tzinfo=None),
                    ends.astimezone(utc_tz).replace(tzinfo=None),
                )
            )

        log.info(
            f"Got {len(occurrences)} occurrences for date range: ({local_starts_range} - {utc_until})",
            occurrences=occurrences,
        )
        return occurrences

    @staticmethod
    def _convert_datetime_to_tz(
        unaware_datetime: datetime.datetime,
        member_timezone: str,
    ) -> datetime.datetime:
        utc_tz = tz.gettz("UTC")
        unaware_datetime.replace(tzinfo=utc_tz)
        member_tz = tz.gettz(member_timezone)
        return unaware_datetime.astimezone(member_tz)

    def delete_schedule_recurring_block(
        self,
        schedule_recurring_block_id: int,
        user_id: int,
    ) -> int:
        """
        Delete automatically handles deleting related ScheduleEvents due to
        cascaded deletes on ScheduleRecurringBlock
        """
        self.detect_booked_appointments_in_block(
            schedule_recurring_block_id=schedule_recurring_block_id,
            user_id=user_id,
        )
        return self.schedule_recurring_block_repo.delete(id=schedule_recurring_block_id)
