from __future__ import annotations

import dataclasses
from datetime import datetime


@dataclasses.dataclass
class MPracticeTemplate:
    id: int
    owner_id: int
    title: str
    text: str
    is_global: bool
    sort_order: int
    created_at: datetime
    modified_at: datetime


@dataclasses.dataclass
class PostMPracticeTemplate:
    title: str
    text: str
    is_global: bool
    sort_order: int


@dataclasses.dataclass
class MPracticeTemplateLitePagination:
    order_direction: str
    total: int
