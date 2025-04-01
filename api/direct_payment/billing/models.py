from __future__ import annotations

import dataclasses
import datetime
import enum
import uuid
from collections import namedtuple
from typing import Literal

from direct_payment.billing.constants import (
    CONTACT_CARD_ISSUER,
    INSUFFICIENT_FUNDS,
    OTHER_MAVEN,
    PAYMENT_METHOD_HAS_EXPIRED,
    REQUIRES_AUTHENTICATE_PAYMENT,
    UNKNOWN,
)


class BillStatus(enum.Enum):
    # Initial State
    NEW = "NEW"
    # Transitory States
    PROCESSING = "PROCESSING"
    # Final States
    PAID = "PAID"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BillErrorTypes(enum.Enum):
    CONTACT_CARD_ISSUER = CONTACT_CARD_ISSUER
    INSUFFICIENT_FUNDS = INSUFFICIENT_FUNDS
    OTHER_MAVEN = OTHER_MAVEN
    PAYMENT_METHOD_HAS_EXPIRED = PAYMENT_METHOD_HAS_EXPIRED
    REQUIRES_AUTHENTICATE_PAYMENT = REQUIRES_AUTHENTICATE_PAYMENT
    UNKNOWN = UNKNOWN


class BillMetadataKeys(enum.Enum):
    BILL_ATTEMPT = "bill_attempt"
    BILL_UUID = "bill_uuid"
    COPAY_PASSTHROUGH = "copay_passthrough"
    INITIATED_BY = "initiated_by"
    PAYER_TYPE = "payer_type"
    RECOUPED_FEE = "recouped_fee"
    SOURCE_TYPE = "source_type"
    SOURCE_ID = "source_id"
    PAYMENT_METHOD_TYPE = "payment_method_type"
    PAYMENT_METHOD_ID = "payment_method_id"


UPCOMING_STATUS = [BillStatus.NEW, BillStatus.PROCESSING, BillStatus.FAILED]

HISTORIC_STATUS = [BillStatus.PAID, BillStatus.REFUNDED]


class PayorType(enum.Enum):
    MEMBER = "MEMBER"
    EMPLOYER = "EMPLOYER"
    CLINIC = "CLINIC"


class PaymentMethod(enum.Enum):
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    WRITE_OFF = "WRITE_OFF"
    OFFLINE = "OFFLINE"


@dataclasses.dataclass
class Bill:
    uuid: uuid.UUID
    amount: int
    last_calculated_fee: int | None
    label: str | None
    payor_type: PayorType
    payor_id: int
    procedure_id: int
    cost_breakdown_id: int
    status: BillStatus
    payment_method: PaymentMethod
    payment_method_id: str | None
    payment_method_type: PaymentMethodType | None
    id: int | None = None
    payment_method_label: str | None = None
    error_type: str | None = None
    reimbursement_request_created_at: datetime.datetime | None = None
    card_funding: CardFunding | None = None
    display_date: str = "created_at"
    # default fields
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None
    # state machine tracking
    processing_at: datetime.datetime | None = None
    paid_at: datetime.datetime | None = None
    refunded_at: datetime.datetime | None = None
    failed_at: datetime.datetime | None = None
    cancelled_at: datetime.datetime | None = None
    refund_initiated_at: datetime.datetime | None = None
    processing_scheduled_at_or_after: datetime.datetime | None = None
    # Ephemeral flag
    is_ephemeral: bool = False


ProcessingRecordTypeT = Literal[
    "payment_gateway_event",
    "payment_gateway_request",
    "payment_gateway_response",
    "billing_service_workflow",
    "admin_billing_workflow",
    "manual_billing_correction",
]


@dataclasses.dataclass
class BillProcessingRecord:
    processing_record_type: ProcessingRecordTypeT
    body: dict
    bill_id: int
    bill_status: BillStatus
    # bill_payment_method_label: str | None = None PAY-4284
    transaction_id: uuid.UUID | None = None
    created_at: datetime.datetime | None = None
    id: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")


class BillStateMachine:
    BillTransition = namedtuple("BillTransition", ["source_status", "target_status"])

    state_machine = frozenset(
        {  # allowed combinations of status changes
            BillTransition(None, BillStatus.NEW),
            BillTransition(BillStatus.NEW, BillStatus.PROCESSING),
            BillTransition(BillStatus.NEW, BillStatus.CANCELLED),
            BillTransition(BillStatus.PROCESSING, BillStatus.FAILED),
            BillTransition(BillStatus.PROCESSING, BillStatus.PROCESSING),
            BillTransition(BillStatus.FAILED, BillStatus.PAID),
            BillTransition(BillStatus.FAILED, BillStatus.PROCESSING),
            BillTransition(BillStatus.FAILED, BillStatus.CANCELLED),
            BillTransition(BillStatus.PROCESSING, BillStatus.PAID),
            BillTransition(BillStatus.PROCESSING, BillStatus.REFUNDED),
        }
    )

    @staticmethod
    def is_valid_transition(
        source_status: BillStatus | None, target_status: BillStatus | None
    ) -> bool:
        return (
            source_status == target_status
            or (source_status, target_status) in BillStateMachine.state_machine
        )


@dataclasses.dataclass
class PaymentMethodInformation:
    payment_method_type: PaymentMethodType
    payment_method_id: str
    payment_method_last4: str
    card_funding: CardFunding | None = None


class PaymentMethodType(enum.Enum):
    card = "card"
    us_bank_account = "us_bank_account"


class CardFunding(enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    PREPAID = "PREPAID"
    UNKNOWN = "UNKNOWN"


@dataclasses.dataclass
class MemberBillEstimateInfo:
    estimate: Bill | None
    bill: Bill | None
    should_caller_commit: bool
    should_caller_notify_of_bill: bool
