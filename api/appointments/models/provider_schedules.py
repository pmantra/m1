from __future__ import annotations

import dataclasses
import datetime

from appointments.models.constants import ScheduleFrequencies, ScheduleStates


@dataclasses.dataclass
class ProviderScheduleRecurringBlock:
    schedule_id: int
    id: int
    starts_at: datetime.datetime
    ends_at: datetime.datetime
    frequency: ScheduleFrequencies
    week_days_index: list[int] | None = None
    until: datetime.datetime | None = None
    latest_date_events_created: datetime.datetime | None = None
    schedule_events: list[ProviderScheduleEvent] | None = None


@dataclasses.dataclass
class ProviderScheduleEvent:
    id: int
    state: ScheduleStates | None = None
    starts_at: datetime.datetime | None = None
    ends_at: datetime.datetime | None = None
    schedule_recurring_block_id: int | None = None
