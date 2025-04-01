from __future__ import annotations

import dataclasses
import datetime

__all__ = ("UserActivity",)


@dataclasses.dataclass
class UserActivity:
    user_id: int
    activity_type: str
    id: int | None = None
    activity_date: datetime.datetime | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None
