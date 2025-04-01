from __future__ import annotations

import dataclasses
import datetime

__all__ = ("MemberPreference",)


@dataclasses.dataclass
class MemberPreference:
    value: str
    member_id: int
    preference_id: int
    id: int | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None
