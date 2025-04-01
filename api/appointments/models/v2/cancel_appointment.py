from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from appointments.services.common import obfuscate_appointment_id
from utils.log import logger

log = logger(__name__)


@dataclass
class CancelAppointmentStruct:
    id: int
    member_id: int
    practitioner_id: int
    product_id: int
    scheduled_start: datetime
    scheduled_end: datetime
    product_price: Decimal
    cancelled_at: datetime | None
    member_started_at: datetime | None = None
    member_ended_at: datetime | None = None
    practitioner_started_at: datetime | None = None
    practitioner_ended_at: datetime | None = None
    disputed_at: datetime | None = None
    json_str: str | None = None

    def __post_init__(self) -> None:
        self.appointment_id = obfuscate_appointment_id(self.id)


@dataclass
class CancellationPolicyStruct:
    id: int
    name: str
    refund_0_hours: int
    refund_2_hours: int
    refund_6_hours: int
    refund_12_hours: int
    refund_24_hours: int
    refund_48_hours: int
