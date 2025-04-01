from __future__ import annotations

import dataclasses
import enum
from datetime import datetime


class OrderDirection(str, enum.Enum):
    ASC = "asc"
    DESC = "desc"


@dataclasses.dataclass
class ProviderAppointmentFilter:
    practitioner_id: int | None = None
    member_id: int | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    schedule_event_ids: list[int] | None = None
    exclude_statuses: list[str] | None = None


@dataclasses.dataclass
class Pagination:
    order_direction: str
    limit: int
    offset: int
    total: int
