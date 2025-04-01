import enum
from typing import Dict, Literal

from flask_babel import lazy_gettext

DisplayDatesT = Literal["created_at", "due_at", "completed_at"]
PaymentStatusT = Literal[
    "NEW", "PENDING", "PROCESSING", "FAILED", "PAID", "REFUNDED", "CANCELLED", "VOIDED"
]
CostResponsibilityT = Literal["shared", "no_member", "member_only"]

ALERT_LABEL_TEXT = (
    "This procedure was cancelled. "
    "If applicable, your full payment will be refunded to your original payment method."
)
ESTIMATED_BOILERPLATE = lazy_gettext("payments_mmb_estimated_initial")


class EstimateText(enum.Enum):
    DEFAULT = lazy_gettext("payments_mmb_estimated_bill")
    ESTIMATED_TOTAL = lazy_gettext("payments_mmb_estimated_len_obj")


class PaymentText(enum.Enum):
    DEFAULT = lazy_gettext("payments_mmb_estimated_total_cost")
    EMPLOYER = lazy_gettext("payments_mmb_fully_covered")


class DetailLabel(enum.Enum):
    COINSURANCE = lazy_gettext("payments_mmb_coinsurance")
    COPAY = lazy_gettext("payments_mmb_copay")
    DEDUCTIBLE = lazy_gettext("payments_mmb_deductible")
    FEES = lazy_gettext("payments_mmb_fees")
    NOT_COVERED = lazy_gettext("payments_mmb_not_covered")
    HRA_APPLIED = lazy_gettext("payments_mmb_hra_applied")
    HRA_CREDIT = lazy_gettext("payments_mmb_hra_credit")
    MAVEN_BENEFIT = lazy_gettext("payments_mmb_maven_benefit")
    MEDICAL_PLAN = lazy_gettext("payments_mmb_medical_plan")
    TOTAL_MEMBER_RESPONSIBILITY = lazy_gettext(
        "payments_mmb_total_member_responsibility"
    )
    PREVIOUS_CHARGES = lazy_gettext("payments_mmb_previous_charges")
    ESTIMATE_ADJUSTMENT = lazy_gettext("payments_mmb_estimate_adjustment")


class EstimateTitles(enum.Enum):
    YOUR_RESPONSIBILITY = lazy_gettext("payments_mmb_estimate_responsibility")
    COVERED_AMOUNT = lazy_gettext("payments_mmb_covered_amount")


class CaptionLabels(enum.Enum):
    FULL_COST_COVERED = lazy_gettext("payments_mmb_full_cost_covered")
    REMAINING_COST_COVERED = lazy_gettext("payments_mmb_remaining_cost_covered")


subtitles: Dict = {
    "NEW": lazy_gettext("payments_mmb_due_billed_date"),
    "PROCESSING": lazy_gettext("payments_mmb_computed_billed_date"),
    "PENDING": lazy_gettext("payments_mmb_calculating_date"),
    "PAID": lazy_gettext("payments_mmb_computed_billed_date"),
    # PAID_NO_MEMBER_COST is not a PaymentStatusT, but a special case.
    "PAID_NO_MEMBER_COST": lazy_gettext("payments_mmb_computed_date"),
    "FAILED": lazy_gettext("payments_mmb_due_date"),
    "REFUNDED": lazy_gettext("payments_mmb_returned_date"),
    "CANCELLED": lazy_gettext("payments_mmb_computed_date"),
    "VOIDED": lazy_gettext("payments_mmb_voided_date"),
}

# ======= Feature flags =======
ENABLE_UNLIMITED_BENEFITS_FOR_PAYMENTS_HELPER = "unlimited-benefits-payments-helper"
