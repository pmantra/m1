import dataclasses
import datetime
import enum
from typing import Optional


class PlanType(enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    FAMILY = "FAMILY"


class Source(enum.Enum):
    MAVEN = "MAVEN"
    ESI = "ESI"


@dataclasses.dataclass
class HealthPlanYearToDateSpend:
    policy_id: str
    year: int
    first_name: str
    last_name: str
    source: Source
    plan_type: PlanType = PlanType.INDIVIDUAL
    deductible_applied_amount: int = 0
    oop_applied_amount: int = 0
    # Note: The only reason I mark id as optional here is that I want MySQL to auto increment id
    id: Optional[int] = None
    bill_id: Optional[int] = None
    transmission_id: Optional[int] = None
    transaction_filename: Optional[str] = None
    created_at: Optional[datetime.datetime] = dataclasses.field(
        default_factory=datetime.datetime.utcnow
    )
    modified_at: Optional[datetime.datetime] = dataclasses.field(
        default_factory=datetime.datetime.utcnow
    )
