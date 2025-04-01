from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Optional

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, Column, Text

from models.base import ModelBase
from utils.data import JSONAlchemy


class RTETransaction(ModelBase):
    __tablename__ = "rte_transaction"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_health_plan_id = Column(
        BigInteger,
        nullable=False,
        doc="patient health plan used to query RTE api",
    )
    response_code = Column(BigInteger, nullable=False)
    request = Column(JSONAlchemy(Text), nullable=False)
    response = Column(JSONAlchemy(Text), nullable=True)
    plan_active_status = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    time = Column(TIMESTAMP, nullable=False)
    trigger_source = Column(Text, nullable=True)


@dataclasses.dataclass
class EligibilityInfo:
    individual_deductible: int | None = None
    individual_deductible_remaining: int | None = None
    family_deductible: int | None = None
    family_deductible_remaining: int | None = None
    individual_oop: int | None = None
    individual_oop_remaining: int | None = None
    family_oop: int | None = None
    family_oop_remaining: int | None = None
    coinsurance: Decimal | None = None
    coinsurance_min: int | None = None
    coinsurance_max: int | None = None
    copay: int | None = None
    ignore_deductible: bool | None = False
    max_oop_per_covered_individual: int | None = None
    hra_remaining: int | None = None
    is_deductible_embedded: bool | None = None
    is_oop_embedded: bool | None = None


@dataclasses.dataclass
class RxYTDInfo:
    family_ytd_deductible: int
    family_ytd_oop: int
    ind_ytd_deductible: int
    ind_ytd_oop: int


@dataclasses.dataclass
class TieredRTEErrorData:
    attr_name: str
    coverage_value: Optional[int]
    rte_value: Optional[int]
