from __future__ import annotations

import datetime
import functools
from typing import List

import ddtrace
import sqlalchemy as sa
import sqlalchemy.orm.scoping

from appointments.models.provider_schedules import (
    ProviderScheduleEvent,
    ProviderScheduleRecurringBlock,
)
from appointments.models.schedule_event import ScheduleEvent
from appointments.models.schedule_recurring_block import (
    ScheduleRecurringBlock,
    ScheduleRecurringBlockWeekdayIndex,
)
from appointments.utils import query_utils
from common import stats
from storage.connection import db
from storage.repository import base
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)
metric_prefix = "api.appointments.repository.schedules"

__all__ = ("ScheduleRecurringBlockRepository", "ScheduleEventRepository")


class ScheduleRecurringBlockRepository(
    base.BaseRepository[ProviderScheduleRecurringBlock]
):
    """A repository for managing ScheduleRecurringBlock, ScheduleRecurringWeekdayIndex and ScheduleEvents"""

    model = ProviderScheduleRecurringBlock

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "appointments/repository/queries/schedule_recurring_block.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 7:
            raise MissingQueryError()

        self._get_schedule_recurring_blocks_query = queries[0]
        self._get_schedule_recurring_block_query = queries[1]
        self._get_schedule_recurring_block_by_id_query = queries[2]
        self._get_schedule_recurring_block_by_schedule_event_query = queries[3]
        self._get_schedule_recurring_block_weekday_index_by_schedule_recurring_block_id = queries[
            4
        ]
        self._get_schedule_event_by_schedule_recurring_block_id = queries[5]
        self._get_existing_appointments_in_schedule_recurring_block = queries[6]

    def get_schedule_recurring_blocks(
        self, user_id: int, starts_at: datetime.datetime, until: datetime.datetime
    ) -> List[ProviderScheduleRecurringBlock]:
        # The where clause follows looks for intersecting recurring blocks
        # refer to existing_events() on ScheduleEvent that the logic mimics
        rows = self.session.execute(
            self._get_schedule_recurring_blocks_query,
            {"user_id": user_id, "starts_at": starts_at, "until": until},
        ).fetchall()

        provider_schedule_recurring_blocks = [
            ProviderScheduleRecurringBlock(**row) for row in rows
        ]
        return self._get_week_day_index_schedule_events_for_schedule_recurring_blocks(
            provider_schedule_recurring_blocks
        )

    def get_schedule_recurring_block(
        self,
        user_id: int,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        until: datetime.datetime,
    ) -> ProviderScheduleRecurringBlock | None:
        """
        Gets an exact matching (user_id, starts_at, ends_at, until) recurring block
        """
        result = self.session.execute(
            self._get_schedule_recurring_block_query,
            {
                "user_id": user_id,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "until": until,
            },
        ).fetchone()

        if not result:
            return None

        provider_schedule_recurring_blocks = [ProviderScheduleRecurringBlock(**result)]
        return self._get_week_day_index_schedule_events_for_schedule_recurring_blocks(
            provider_schedule_recurring_blocks
        )[0]

    def get_schedule_recurring_block_by_id(
        self, schedule_recurring_block_id: int
    ) -> ProviderScheduleRecurringBlock | None:
        result = self.session.execute(
            self._get_schedule_recurring_block_by_id_query,
            {"schedule_recurring_block_id": schedule_recurring_block_id},
        ).fetchone()

        if not result:
            return None

        provider_schedule_recurring_blocks = [ProviderScheduleRecurringBlock(**result)]
        return self._get_week_day_index_schedule_events_for_schedule_recurring_blocks(
            provider_schedule_recurring_blocks
        )[0]

    def get_schedule_recurring_block_by_schedule_event(
        self, schedule_event_id: int
    ) -> List[ProviderScheduleRecurringBlock]:
        rows = self.session.execute(
            self._get_schedule_recurring_block_by_schedule_event_query,
            {"schedule_event_id": schedule_event_id},
        ).fetchall()

        provider_schedule_recurring_blocks = [
            ProviderScheduleRecurringBlock(**row) for row in rows
        ]
        return self._get_week_day_index_schedule_events_for_schedule_recurring_blocks(
            provider_schedule_recurring_blocks
        )

    def _get_week_day_index_schedule_events_for_schedule_recurring_blocks(
        self,
        schedule_recurring_block_rows: List[ProviderScheduleRecurringBlock],
    ) -> List[ProviderScheduleRecurringBlock]:
        for block in schedule_recurring_block_rows:
            week_day_index_rows = self.session.execute(
                self._get_schedule_recurring_block_weekday_index_by_schedule_recurring_block_id,
                {"schedule_recurring_block_id": block.id},
            ).fetchall()
            if len(week_day_index_rows) > 0:
                week_day_indices = [value for value, in week_day_index_rows]
                block.week_days_index = week_day_indices

            schedule_event_rows = self.session.execute(
                self._get_schedule_event_by_schedule_recurring_block_id,
                {"schedule_recurring_block_id": block.id},
            ).fetchall()
            if len(schedule_event_rows) > 0:
                block.schedule_events = [
                    ProviderScheduleEvent(**row) for row in schedule_event_rows
                ]
        return schedule_recurring_block_rows

    def get_count_existing_appointments_in_schedule_recurring_block(
        self, user_id: int, starts_at: datetime.datetime, ends_at: datetime.datetime
    ) -> int:
        # refer to _existing_appointments() which this logic mimics
        result = self.session.execute(
            self._get_existing_appointments_in_schedule_recurring_block,
            {
                "user_id": user_id,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "now": datetime.datetime.utcnow(),
            },
        ).fetchone()

        return result[0]

    @trace_wrapper
    def create(  # type: ignore[override]
        self,
        *,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        frequency: str,
        until: datetime.datetime,
        schedule_id: int,
        week_days_index: list[int],
    ) -> ProviderScheduleRecurringBlock | None:
        schedule_recurring_block = ScheduleRecurringBlock(
            starts_at=starts_at,
            ends_at=ends_at,
            frequency=frequency,
            until=until,
            schedule_id=schedule_id,
        )
        self.session.add(schedule_recurring_block)

        try:
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to create schedule_recurring_block record",
                error=str(e),
            )
            stats.increment(
                metric_name=f"{metric_prefix}.schedule_recurring_block.create",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["error:true"],
            )
            return None

        for index in week_days_index:
            week_day_index = ScheduleRecurringBlockWeekdayIndex(
                week_days_index=index,
                schedule_recurring_block_id=schedule_recurring_block.id,
            )
            self.session.add(week_day_index)

        try:
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to create schedule_recurring_block_weekday_index record",
                error=str(e),
            )
            stats.increment(
                metric_name=f"{metric_prefix}.schedule_recurring_block_weekday_index.create",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["error:true"],
            )
            return None

        recurring_block = ProviderScheduleRecurringBlock(
            id=schedule_recurring_block.id,
            schedule_id=schedule_recurring_block.schedule.id,
            starts_at=schedule_recurring_block.starts_at,
            ends_at=schedule_recurring_block.ends_at,
            frequency=schedule_recurring_block.frequency,  # type: ignore[arg-type] # Argument "frequency" to "ProviderScheduleRecurringBlock" has incompatible type "str"; expected "ScheduleFrequencies"
            week_days_index=[
                index.week_days_index
                for index in schedule_recurring_block.week_day_indices
            ],
            until=schedule_recurring_block.until,
        )
        return recurring_block

    @trace_wrapper
    def update_latest_date_events_created(
        self,
        schedule_recurring_block_id: int,
        date: datetime.datetime,
    ) -> ProviderScheduleRecurringBlock | None:
        existing_block = self.session.query(ScheduleRecurringBlock).get(
            schedule_recurring_block_id
        )
        if existing_block is None:
            log.error(
                f"Failed to find matching schedule_recurring_block for {schedule_recurring_block_id}"
            )
            stats.increment(
                metric_name=f"{metric_prefix}.schedule_recurring_block_weekday_index.update_latest_date_events_created",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["error:true"],
            )
            return None
        existing_block.latest_date_events_created = date
        self.session.add(existing_block)

        try:
            self.session.commit()
        except Exception as e:
            log.error(
                f"Failed to update latest_date_events_created for schedule_recurring_block: {existing_block.id}",
                error=str(e),
            )
            stats.increment(
                metric_name=f"{metric_prefix}.schedule_recurring_block_weekday_index.update_latest_date_events_created",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["error:true"],
            )
            return None

        updated_existing_block = ProviderScheduleRecurringBlock(
            id=existing_block.id,
            schedule_id=existing_block.schedule.id,
            starts_at=existing_block.starts_at,
            ends_at=existing_block.ends_at,
            frequency=existing_block.frequency,  # type: ignore[arg-type] # Argument "frequency" to "ProviderScheduleRecurringBlock" has incompatible type "str"; expected "ScheduleFrequencies"
            until=existing_block.until,
            latest_date_events_created=existing_block.latest_date_events_created,
        )

        updated_existing_block = (
            self._get_week_day_index_schedule_events_for_schedule_recurring_blocks(
                [updated_existing_block]
            )[0]
        )

        return updated_existing_block

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sa.Table:
        return ScheduleRecurringBlock.__table__

    @classmethod
    def table_name(cls) -> str:
        return ScheduleRecurringBlock.__tablename__

    @staticmethod
    def table_columns() -> tuple[sa.Column, ...]:
        # This function is only used during BaseRepository.make_table,
        # which is being overridden here, so there is no need implement table_columns()
        return ()


class ScheduleEventRepository(base.BaseRepository[ProviderScheduleEvent]):
    """A repository for managing ScheduleEvents"""

    model = ProviderScheduleEvent

    @trace_wrapper
    def create(  # type: ignore[override]
        self,
        *,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        schedule_recurring_block_id: int,
    ) -> ProviderScheduleEvent | None:
        # find matching schedule
        schedule = (
            db.session.query(ScheduleRecurringBlock)
            .get(schedule_recurring_block_id)
            .schedule
        )

        schedule_event = ScheduleEvent(
            starts_at=starts_at,
            ends_at=ends_at,
            schedule=schedule,
            schedule_recurring_block_id=schedule_recurring_block_id,
        )
        self.session.add(schedule_event)

        try:
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to create schedule_events record",
                error=str(e),
            )
            stats.increment(
                metric_name=f"{metric_prefix}.schedule_event.create",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["error:true"],
            )
            return None

        provider_schedule_event = ProviderScheduleEvent(
            id=schedule_event.id,
            starts_at=schedule_event.starts_at,
            ends_at=schedule_event.ends_at,
            schedule_recurring_block_id=schedule_event.schedule_recurring_block_id,
        )
        return provider_schedule_event

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sa.Table:
        return ScheduleEvent.__table__

    @classmethod
    def table_name(cls) -> str:
        return ScheduleEvent.__tablename__

    @staticmethod
    def table_columns() -> tuple[sa.Column, ...]:
        # This function is only used during BaseRepository.make_table,
        # which is being overridden here, so there is no need implement table_columns()
        return ()


class QueryNotFoundError(Exception):
    ...


class MissingQueryError(Exception):
    ...
