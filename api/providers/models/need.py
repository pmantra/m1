import dataclasses
from typing import Optional


@dataclasses.dataclass
class Need:
    id: int
    name: str
    description: str
    slug: Optional[str] = None
    display_order: Optional[int] = None
