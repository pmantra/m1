from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Column, DateTime, Float, Integer, String

from models.base import ModelBase


class Process(Enum):
    ADMIN = "ADMIN"
    INVOICE_GENERATOR = "INVOICE_GENERATOR"


@dataclass
class OrganizationInvoicingSettings:
    """The invoice settings as they apply to the organization."""

    uuid: UUID
    """Unique external id. UUID4 format."""

    organization_id: int
    """ID of the org."""

    created_by_user_id: int
    """user_id that created the record"""

    updated_by_user_id: int
    """user_id that updated the record"""

    invoicing_active_at: datetime | None
    """The date at which the employer activated invoice based billing."""

    invoice_cadence: str | None
    """Invoice generation cadence in CRON format. application will ignore hh mm."""

    bill_processing_delay_days: int | None
    """Bills will be processed bill_processing_delay_days after bill creation."""

    bill_cutoff_at_buffer_days: int | None
    """The cutoff offset in days from the current date for the latest bill creation date."""

    # The following fields are set by the DB
    id: int | None = None
    """Unique internal id."""

    created_at: datetime | None = None
    """The time at which this record was created."""

    updated_at: datetime | None = None
    """The time at which this record was updated."""


@dataclass
class DirectPaymentInvoice:
    """An invoice - linked to a reimbursement org setting and to 0 or more bills ."""

    uuid: UUID
    """Unique external id (UUID4)"""

    created_by_process: Process
    """The process that created the invoice."""

    created_by_user_id: int | None
    """User id that created the record (if creation was via admin)"""

    reimbursement_organization_settings_id: int
    """ID of the reimbursement organisation settings."""

    bill_creation_cutoff_start_at: datetime
    """Start time (inclusive) of the bill sweep-in time window. (UTC)"""

    bill_creation_cutoff_end_at: datetime
    """End time (inclusive) of the bill sweep-in time window. (UTC)"""

    bills_allocated_at: datetime | None = None
    """The time at which bills were allocated to this invoice."""

    bills_allocated_by_process: Process | None = None
    """The process that allocated bills to the invoice."""

    voided_at: datetime | None = None
    """The time at which this invoice was voided.(UTC). Used for soft delete."""

    voided_by_user_id: int | None = None
    """User_id that voided the record (if the record was voided)"""

    report_generated_at: datetime | None = None
    """The time at which the report was generated. UTC"""

    report_generated_json: str | None = None
    """The generated report stored in JSON format (unenforced by db)"""

    bill_allocated_by_user_id: int | None = None
    """User id that allocated the bills (if allocation was via admin)"""

    # The following fields are set by the DB
    id: int | None = None
    """Unique internal id."""

    created_at: datetime | None = None
    """The time at which this record was created."""


class OrgDirectPaymentInvoiceReport(ModelBase):
    __tablename__ = "org_direct_payment_invoice_report"

    id = Column("id", String, primary_key=True)

    organization_id = Column(Integer, nullable=False)

    organization_name = Column(String, nullable=False)

    ros_invoice_ids = Column(String, nullable=False)

    bill_creation_cutoff_start_at = Column(DateTime, nullable=False)

    bill_creation_cutoff_end_at = Column(DateTime, nullable=False)

    total_medical_cost_in_dollars = Column(Float, nullable=False)

    total_pharmacy_cost_in_dollars = Column(Integer, nullable=False)


@dataclass
class DirectPaymentInvoiceBillAllocation:
    """An allocation of a bill to an invoice."""

    uuid: UUID
    """Unique external id (UUID4)"""

    created_by_process: Process
    """One of: ADMIN, INVOICE_GENERATOR"""

    created_by_user_id: int | None
    """User id that created the row(if creation was via admin)"""

    direct_payment_invoice_id: int
    """invoice internal id"""

    bill_uuid: UUID
    """Bill external id (UUID4)."""

    # The following fields are set by the DB
    id: int = 0
    """Unique internal id."""

    created_at: datetime | None = None
    """The time at which this record was created."""


class BillType(Enum):
    MEDICAL = "MEDICAL"
    PHARMACY = "PHARMACY"


@dataclass
class BillInformation:
    uuid: UUID
    bill_created_at: datetime
    bill_amount: str
    bill_type: BillType


@dataclass
class BillingReport:
    organisation_name: str
    organisation_id: int
    report_generated_at: datetime
    report_cadence: str
    start_date_time: datetime
    end_date_time: datetime
    total_bills: int
    total_bill_amount: str
    clinic_bill_amount: str | None
    pharmacy_bill_amount: str | None
    bill_information: list[BillInformation] | None
