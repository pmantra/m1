from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from cost_breakdown.constants import AmountType, ClaimType, CostBreakdownType, Tier
from cost_breakdown.models.rte import EligibilityInfo, RTETransaction
from models.base import (
    ModelBase,
    TimeLoggedExternalUuidModelBase,
    TimeLoggedSnowflakeModelBase,
)
from utils.data import JSONAlchemy
from wallet.models.reimbursement import ReimbursementRequest


class CostBreakdownIrsMinimumDeductible(ModelBase):
    __tablename__ = "irs_minimum_deductible"

    year = Column(SmallInteger, primary_key=True, autoincrement=False)
    individual_amount = Column(Integer, nullable=False)
    family_amount = Column(Integer, nullable=False)


class CostBreakdown(TimeLoggedExternalUuidModelBase):
    __tablename__ = "cost_breakdown"

    id = Column(Integer, primary_key=True)

    treatment_procedure_uuid = Column(
        String(50),
        nullable=True,
        doc="A reference to the treatment procedure the cost breakdown is associated with",
    )
    wallet_id = Column(BigInteger, nullable=False)
    member_id = Column(BigInteger, nullable=True)
    reimbursement_request_id = Column(
        BigInteger,
        nullable=True,
        doc="Reimbursement Request that generates a cost breakdown.",
    )
    is_unlimited = Column(Boolean, nullable=False, default=False)
    total_member_responsibility = Column(
        Integer, nullable=False, doc="Member responsibility amount in cents"
    )
    total_employer_responsibility = Column(
        Integer, nullable=False, doc="Employer responsibility amount in cents"
    )
    beginning_wallet_balance = Column(
        Integer, nullable=False, doc="Beginning wallet balance amount in cents"
    )
    ending_wallet_balance = Column(
        Integer, nullable=False, doc="Ending wallet balance amount in cents"
    )
    deductible = Column(
        Integer, default=0, doc="Member responsibility deductible amount in cents"
    )
    oop_applied = Column(
        Integer, default=0, doc="Member responsibility oop amount in cents"
    )
    hra_applied = Column(Integer, default=0, doc="HRA applied amount in cents")
    coinsurance = Column(
        Integer, default=0, doc="Member responsibility coinsurance amount in cents"
    )
    copay = Column(
        Integer, default=0, doc="Member responsibility copay amount in cents"
    )
    oop_remaining = Column(
        Integer, default=None, doc="Individual member oop remaining in cents"
    )
    overage_amount = Column(
        Integer, default=0, doc="Cost amount exceeding wallet balance in cents"
    )
    deductible_remaining = Column(
        Integer, default=None, nullable=True, doc="Remaining deductible in cents"
    )
    family_deductible_remaining = Column(
        Integer, default=None, nullable=True, doc="Remaining family deductible in cents"
    )
    family_oop_remaining = Column(
        Integer, default=None, nullable=True, doc="Remaining family oop in cents"
    )
    amount_type = Column(
        Enum(AmountType), default=AmountType.INDIVIDUAL, nullable=False
    )
    cost_breakdown_type = Column(Enum(CostBreakdownType), nullable=False)
    calc_config = Column(JSONAlchemy(Text), nullable=True)
    rte_transaction_id = Column(
        BigInteger,
        ForeignKey("rte_transaction.id"),
        nullable=True,
    )
    created_at = Column(TIMESTAMP, nullable=False)
    modified_at = Column(TIMESTAMP, nullable=False)
    rte_transaction = relationship(RTETransaction)


class ReimbursementRequestToCostBreakdown(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_request_to_cost_breakdown"

    claim_type = Column(Enum(ClaimType), nullable=False)

    treatment_procedure_uuid = Column(
        String(36),
        nullable=False,
    )

    reimbursement_request_id = Column(
        BigInteger,
        ForeignKey("reimbursement_request.id"),
        nullable=False,
    )
    reimbursement_request = relationship(ReimbursementRequest)
    cost_breakdown_id = Column(
        BigInteger,
        ForeignKey("cost_breakdown.id"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"ReimbursementRequestToCostBreakdown id:{self.id}, treatment_procedure_uuid:{self.treatment_procedure_uuid}, cost_breakdown_id:{self.cost_breakdown_id}, reimbursement_request_id:{self.reimbursement_request_id}, claim_type:{self.claim_type}"


RteIdType = Optional[int]


@dataclass
class DeductibleAccumulationYTDInfo:
    individual_deductible_applied: int
    individual_oop_applied: int
    family_deductible_applied: int
    family_oop_applied: int


@dataclass
class HDHPAccumulationYTDInfo:
    sequential_member_responsibilities: int
    sequential_family_responsibilities: int


@dataclass
class HealthPlanConfiguration:
    is_deductible_embedded: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    is_oop_embedded: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    is_family_plan: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")


@dataclass
class AdminDetail:
    user_id: int
    email: str


@dataclass
class SystemUser:
    trigger_source: str
    admin_detail: Optional[AdminDetail] = None


@dataclass
class ExtraAppliedAmount:
    oop_applied: int = 0
    wallet_balance_applied: int = 0
    assumed_paid_procedures: List[int] = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "List[int]")


@dataclass
class CalcConfigAudit:
    """
    Audit data for understanding the state of a Cost Breakdown and what was used in the calculation.
    Initialized as empty, with relevant data assigned as the calculation is prepared.
    """

    eligibility_info: Optional[EligibilityInfo] = None
    tier: Optional[Tier] = None
    sequential_date: Optional[str] = None
    sequential_procedure_ids: List[int] = field(default_factory=list)
    sequential_cost_breakdown_ids: List[int] = field(default_factory=list)
    sequential_deductible_accumulation_member_responsibility: Optional[
        DeductibleAccumulationYTDInfo
    ] = None
    sequential_hdhp_member_responsibilities: Optional[HDHPAccumulationYTDInfo] = None
    alegeus_ytd_spend: Optional[int] = None
    hdhp_non_alegeus_sequential_ytd_spend: Optional[int] = None
    rx_ytd_spend: Optional[int] = None
    system_user: Optional[SystemUser] = None
    trigger_object_status: Optional[str] = None
    health_plan_configuration: HealthPlanConfiguration = HealthPlanConfiguration()
    extra_applied_amount: Optional[ExtraAppliedAmount] = None
    should_include_pending: bool = False
    asof_date: Optional[str] = None
    family_asof_date: Optional[str] = None
    member_health_plan_id: Optional[int] = None
    reimbursement_organization_settings_id: Optional[int] = None


@dataclass
class CostBreakdownData:
    """
    Data returned by the CostBreakdownDataService class and only that data.
    Subset of the full CostBreakdown, containing calculated data, but not config or db associations.
    """

    rte_transaction_id: RteIdType
    total_member_responsibility: int
    total_employer_responsibility: int
    beginning_wallet_balance: int
    ending_wallet_balance: int
    cost_breakdown_type: CostBreakdownType
    amount_type: AmountType
    deductible: int = 0
    deductible_remaining: int = 0
    coinsurance: int = 0
    copay: int = 0
    overage_amount: int = 0
    oop_applied: int = 0
    hra_applied: int = 0
    is_unlimited: bool = False
    oop_remaining: Optional[int] = None
    family_deductible_remaining: Optional[int] = None
    family_oop_remaining: Optional[int] = None
