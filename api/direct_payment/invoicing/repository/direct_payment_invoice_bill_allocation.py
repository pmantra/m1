from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from typing import Any, Mapping, Optional

import ddtrace
import sqlalchemy as sa

from direct_payment.billing.models import Bill
from direct_payment.billing.repository import BillRepository
from direct_payment.invoicing import models
from direct_payment.invoicing.repository.common import UUID
from storage.repository import base
from utils.log import logger

log = logger(__name__)

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class DirectPaymentInvoiceBillAllocationRepository(
    base.BaseRepository[models.DirectPaymentInvoiceBillAllocation]  # type: ignore[type-var]
):
    model = models.DirectPaymentInvoiceBillAllocation

    @staticmethod
    def instance_to_values(instance: models.DirectPaymentInvoiceBillAllocation) -> dict:  # type: ignore[type-var] # Type argument "DirectPaymentInvoiceBillAllocation" of "BaseRepository" must be a subtype of "Instance"
        as_dict = dataclasses.asdict(instance)
        # these keys are set by the db so do not let them be inserted or updated
        for key in ["id", "created_at"]:
            _ = as_dict.pop(key, None)
        # special case process
        as_dict["created_by_process"] = as_dict["created_by_process"].value
        return as_dict

    @staticmethod
    def table_columns() -> tuple[sa.Column, ...]:
        # fmt: off
        return (
            sa.Column("id", sa.BigInteger, autoincrement=True, primary_key=True, comment="Unique internal id."),
            sa.Column("uuid", UUID(), nullable=False, unique=True, default=lambda: str(uuid.uuid4()), comment="Unique external id. UUID4 format."),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp(), comment="The time at which this record was created."),
            sa.Column("created_by_process", sa.String(20), nullable=False, comment="One of: ADMIN, INVOICE_GENERATOR"),
            sa.Column("created_by_user_id", sa.Integer, nullable=True, comment="User id that created the row(if creation was via admin)"),
            sa.Column("direct_payment_invoice_id", sa.BigInteger, nullable=False, comment="invoice internal id"),
            sa.Column("bill_uuid", UUID(), nullable=False, comment="Bill external id (UUID4)."),
        )
        # fmt: on

    @classmethod
    def identity_columns(cls) -> tuple[sa.Column, ...]:
        return (sa.Column("id", sa.BigInteger, primary_key=True),)

    @classmethod
    def deserialize(
        cls, row: Optional[Mapping[str, Any]]
    ) -> models.DirectPaymentInvoiceBillAllocation | None:
        if row is None:
            return None

        row_data = dict(row)
        # Mysql stores the UUIDs as a string so translate it here.
        if isinstance(row_data.get("uuid"), str):
            row_data["uuid"] = uuid.UUID(row_data["uuid"])
        if isinstance(row_data.get("bill_uuid"), str):
            row_data["bill_uuid"] = uuid.UUID(row_data["bill_uuid"])

        row_data["created_by_process"] = models.Process(row_data["created_by_process"])
        # The db row may have more fields than the model (post migration for instance) - so protect against this.
        expected_fields = {field.name for field in dataclasses.fields(cls.model)}
        expected_data = {
            column_name: value
            for column_name, value in row_data.items()
            if column_name in expected_fields
        }
        return cls.model(**expected_data)

    @trace_wrapper
    def get_invoice_bills_ready_to_process(self) -> list[Bill]:
        query = """
                        SELECT b.*
                        FROM bill b
                        INNER JOIN direct_payment_invoice_bill_allocation a ON b.uuid = a.bill_uuid
                        WHERE b.payor_type = 'EMPLOYER'
                        AND b.status = 'NEW'
                        AND b.processing_scheduled_at_or_after <= :current_time
                """
        results = self.session.execute(
            query,
            {
                "current_time": datetime.utcnow(),
            },
        ).fetchall()

        to_return = [BillRepository.deserialize(result) for result in results]
        return [item for item in to_return if item is not None]
