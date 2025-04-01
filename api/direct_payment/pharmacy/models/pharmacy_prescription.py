from __future__ import annotations

import dataclasses
import datetime
import enum
from typing import Optional

from wallet.models.constants import (
    CostSharingCategory,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletUserMemberStatus,
)


class PrescriptionStatus(enum.Enum):
    SCHEDULED = "SCHEDULED"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"
    PAID = "PAID"


@dataclasses.dataclass
class PharmacyPrescription:
    status: PrescriptionStatus
    id: int | None = None
    treatment_procedure_id: int | None = None
    reimbursement_request_id: int | None = None
    user_id: int | None = None
    rx_unique_id: str | None = None
    maven_benefit_id: str | None = None
    user_benefit_id: str | None = None
    amount_owed: int | None = None
    ncpdp_number: str | None = None
    ndc_number: str | None = None
    rx_name: str | None = None
    rx_description: str | None = None
    rx_first_name: str | None = None
    rx_last_name: str | None = None
    rx_order_id: str | None = None
    rx_filled_date: datetime.datetime | None = None
    rx_received_date: datetime.datetime | None = None
    scheduled_ship_date: datetime.datetime | None = None
    actual_ship_date: datetime.datetime | None = None
    cancelled_date: datetime.datetime | None = None
    scheduled_json: dict | None = None
    shipped_json: dict | None = None
    cancelled_json: dict | None = None
    reimbursement_json: dict | None = None
    # default fields
    created_at: Optional[datetime.datetime] = dataclasses.field(
        default_factory=datetime.datetime.utcnow
    )
    modified_at: Optional[datetime.datetime] = dataclasses.field(
        default_factory=datetime.datetime.utcnow
    )

    def __hash__(self) -> int:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return hash(self.rx_unique_id)


@dataclasses.dataclass
class ReimbursementPharmacyPrescriptionParams:
    user_benefit_id: str
    status: PrescriptionStatus
    amount_owed: int
    actual_ship_date: datetime.datetime
    rx_filled_date: datetime.datetime
    reimbursement_json: dict


@dataclasses.dataclass
class ScheduledPharmacyPrescriptionParams:
    treatment_procedure_id: int
    maven_benefit_id: str
    status: PrescriptionStatus
    amount_owed: int
    scheduled_ship_date: datetime.datetime
    scheduled_json: dict


@dataclasses.dataclass
class ReimbursementRequestParams:
    label: str
    service_provider: str
    amount: int
    procedure_type: str
    auto_processed: ReimbursementRequestAutoProcessing
    reimbursement_type: ReimbursementRequestType
    service_start_date: datetime.datetime
    service_end_date: datetime.datetime
    state: ReimbursementRequestState
    expense_type: ReimbursementRequestExpenseTypes | None = None
    original_wallet_expense_subtype_id: int | None = None
    wallet_expense_subtype_id: int | None = None
    person_receiving_service: str | None = None
    person_receiving_service_id: int | None = None
    person_receiving_service_member_status: WalletUserMemberStatus | None = None
    cost_sharing_category: CostSharingCategory | None = None
    cost_credit: int | None = None
