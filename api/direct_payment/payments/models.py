from __future__ import annotations

import dataclasses
import datetime
from typing import Optional, Union

from flask_babel import LazyString

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models as billing_models
from direct_payment.billing.models import Bill
from direct_payment.payments.constants import (
    CostResponsibilityT,
    DisplayDatesT,
    PaymentStatusT,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from wallet.schemas.constants import ClientLayout


@dataclasses.dataclass(frozen=True)
class PaymentRecord:
    label: str
    treatment_procedure_id: int
    payment_status: PaymentStatusT
    created_at: datetime.datetime
    bill_uuid: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    payment_method_type: billing_models.PaymentMethod = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "PaymentMethod")
    payment_method_display_label: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    member_responsibility: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    total_cost: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    cost_responsibility_type: CostResponsibilityT = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Literal['shared', 'no_member', 'member_only']")
    due_at: datetime.datetime = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "datetime")
    completed_at: datetime.datetime = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "datetime")
    display_date: DisplayDatesT = "created_at"


@dataclasses.dataclass(frozen=True)
class PaymentRecordForReimbursementWallet:
    """Payment record that is surfaced to the client through the reimbursement_wallet GET endpoint."""

    payment_status: PaymentStatusT
    procedure_id: int
    procedure_title: str
    created_at: datetime.datetime | None
    """Auxiliary field used for sorting, does not surface to the client."""
    due_at: datetime.datetime | None = None
    """Auxiliary field used for sorting, does not surface to the client."""
    bill_uuid: str | None = None
    member_amount: int | None = None
    member_method: str | None = None
    member_date: str | None = None
    benefit_amount: int | None = None
    benefit_date: str | None = None
    benefit_remaining: int | None = None
    error_type: str | None = None
    processing_scheduled_at_or_after: datetime.datetime | None = None


@dataclasses.dataclass(frozen=True)
class UpcomingPaymentSummaryForReimbursementWallet:
    """Summary of payment records surfaced to the client through the reimbursement_wallet GET endpoint."""

    __slots__ = (
        "total_member_amount",
        "member_method",
        "total_benefit_amount",
        "benefit_remaining",
        "procedure_title",
    )
    total_member_amount: int | None
    member_method: str | None
    total_benefit_amount: int | None
    benefit_remaining: int | None
    procedure_title: str | None


@dataclasses.dataclass(frozen=True)
class UpcomingPaymentsAndSummaryForReimbursementWallet:
    """Response that contains the payments and summary for a reimbursement wallet."""

    __slots__ = ("summary", "payments")
    summary: UpcomingPaymentSummaryForReimbursementWallet | None
    payments: list[PaymentRecordForReimbursementWallet]


@dataclasses.dataclass(frozen=True)
class UpcomingPaymentsResultForReimbursementWallet:
    """Response that contains information about the user's upcoming payments."""

    __slots__ = (
        "upcoming_payments_and_summary",
        "client_layout",
        "show_benefit_amount",
        "num_errors",
    )
    upcoming_payments_and_summary: UpcomingPaymentsAndSummaryForReimbursementWallet
    client_layout: ClientLayout
    show_benefit_amount: bool
    num_errors: int


@dataclasses.dataclass(frozen=True)
class DashboardLayoutResult:
    """Response to contain information about member's dashboard."""

    __slots__ = ("client_layout", "show_benefit_amount")

    client_layout: ClientLayout
    show_benefit_amount: bool


@dataclasses.dataclass(frozen=True)
class PaginationInfo:
    """Abstract this to a common models file if reused."""

    __slots__ = ("next_link", "prev_link", "num_pages", "count", "limit", "offset")

    next_link: str | None
    prev_link: str | None
    num_pages: int
    count: int
    limit: int
    offset: int


@dataclasses.dataclass(frozen=True)
class PaymentDetail:
    label: str
    treatment_procedure_id: int
    treatment_procedure_clinic: str
    treatment_procedure_location: str
    treatment_procedure_started_at: datetime.date
    payment_status: PaymentStatusT
    member_responsibility: int
    total_cost: int
    cost_responsibility_type: CostResponsibilityT
    error_type: str
    responsibility_breakdown: list[PaymentDetailBreakdown]
    benefit_breakdown: list[PaymentDetailBreakdown]
    procedure_status: str
    credits_used: int | None
    created_at: datetime.datetime
    due_at: datetime.datetime = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "datetime")
    completed_at: datetime.datetime = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "datetime")


@dataclasses.dataclass(frozen=True)
class PaymentDetailBreakdown:
    __slots__ = ("label", "cost", "original")
    label: str
    cost: int
    original: Optional[int]


@dataclasses.dataclass(frozen=True)
class EstimateSummaryForReimbursementWallet:
    """Summary of estimates surfaced to the client through the reimbursement_wallet GET endpoint."""

    __slots__ = (
        "estimate_text",
        "total_estimates",
        "total_member_estimate",
        "payment_text",
        "estimate_bill_uuid",
    )
    estimate_text: str
    total_estimates: int
    total_member_estimate: str
    payment_text: str
    estimate_bill_uuid: str | None


@dataclasses.dataclass(frozen=True)
class LabelCost:
    """Label and Cost value to include in Breakdown"""

    __slots__ = (
        "label",
        "cost",
    )
    label: str
    cost: str


@dataclasses.dataclass(frozen=True)
class EstimateBreakdown:
    """Label and Cost value to include in Breakdown"""

    __slots__ = (
        "title",
        "total_cost",
        "items",
    )
    title: str
    total_cost: str
    items: list[LabelCost]


@dataclasses.dataclass(frozen=True)
class EstimateDetail:
    """Details of billing estimate for a treatment procedure."""

    __slots__ = (
        "procedure_id",
        "bill_uuid",
        "procedure_title",
        "clinic",
        "clinic_location",
        "estimate_creation_date",
        "estimate_creation_date_raw",
        "estimated_member_responsibility",
        "estimated_total_cost",
        "estimated_boilerplate",
        "credits_used",
        "responsibility_breakdown",
        "covered_breakdown",
    )
    procedure_id: int
    bill_uuid: str
    procedure_title: str
    clinic: str
    clinic_location: str
    estimate_creation_date: str
    estimate_creation_date_raw: datetime.datetime  # will be isoformatted in output deserializers
    estimated_member_responsibility: str
    estimated_total_cost: str
    estimated_boilerplate: Union[str, LazyString]
    credits_used: str | None
    responsibility_breakdown: EstimateBreakdown
    covered_breakdown: EstimateBreakdown


@dataclasses.dataclass
class BillProcedureCostBreakdown:
    bill: Bill
    procedure: TreatmentProcedure
    cost_breakdown: CostBreakdown
