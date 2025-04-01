from __future__ import annotations

import dataclasses
import datetime

__all__ = ("Preference",)


@dataclasses.dataclass
class Preference:
    name: str
    type: str
    id: int | None = None
    default_value: str | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None
