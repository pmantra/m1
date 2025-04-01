import enum
from dataclasses import dataclass
from typing import Optional


class ActivityType(str, enum.Enum):
    READ = "read"
    MEET = "meet"
    WATCH = "watch"
    CHECK_IN = "check-in"


@dataclass
class ActivityAutoCompleteArgs:
    type: ActivityType
    # used in autocomplete metrics & logs to track where CPS call came from
    caller: str
    # to match READ and WATCH (Mono/Content Article)
    resource_id: Optional[int] = None
    # to match CHECK_IN (HDC Assessment), also as secondary to match READ/WATCH
    slug: Optional[str] = None
    # to match MEET (Mono Appointment), one of these two:
    vertical_id: Optional[int] = None
    appointment_purpose: Optional[str] = None
