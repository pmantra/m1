from __future__ import annotations

import dataclasses
import enum
from typing import Literal


class TreatmentAccumulationStatus(enum.Enum):
    PAID = "PAID"
    REFUNDED = "REFUNDED"
    WAITING = "WAITING"
    ROW_ERROR = "ROW_ERROR"
    SUBMITTED = "SUBMITTED"
    PROCESSED = "PROCESSED"
    SKIP = "SKIP"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


# Payers that are currently supported by RTE
class PayerName(enum.Enum):
    AETNA = "aetna"
    ANTHEM = "anthem"
    BCBS_MA = "bcbs_ma"
    BLUE_EXCHANGE = "blue_exchange"
    Cigna = "cigna"
    CIGNA_TRACK_1 = "cigna_track_1"
    CREDENCE = "credence"  # BCBS AL
    ESI = "esi"
    INDEPENDENCE_BLUE_CROSS = "independence_blue_cross"
    KAISER = "kaiser"
    LUMINARE = "luminare"
    PREMERA = "premera"  # BCBS WA
    SUREST = "surest"
    UHC = "uhc"


# Payers that are currently supported by accumulation
PayerNameT = Literal[
    "aetna",
    "anthem",
    "bcbs_ma",
    "blue_exchange",
    "cigna",
    "cigna_track_1",
    "credence",
    "esi",
    "independence_blue_cross",
    "kaiser",
    "luminare",
    "premera",
    "surest",
    "uhc",
]


class OrganizationName(enum.Enum):
    AMAZON = "Amazon_US"
    GOLDMAN = "Goldman_Sachs"


@dataclasses.dataclass
class DetailWrapper:
    unique_id: str
    line: str
    transaction_id: str | None = (
        None  # set when this specific field is used by the payer
    )


@dataclasses.dataclass
class DetailMetadata:
    is_response: bool
    is_rejection: bool
    should_update: bool
    member_id: str
    unique_id: str
    response_status: str
    response_code: str
    response_reason: str
