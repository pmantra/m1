from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Mapping, Optional

import ddtrace
import sqlalchemy as sa
from sqlalchemy import DECIMAL, Column, DateTime, String, alias, text
from sqlalchemy.engine import ResultProxy
from sqlalchemy.orm import Query

from direct_payment.invoicing import models
from direct_payment.invoicing.repository.common import UUID
from storage.repository import base
from utils.log import logger

log = logger(__name__)

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class DirectPaymentInvoiceRepository(
    base.BaseRepository[models.DirectPaymentInvoice]  # type: ignore[type-var]
):
    model = models.DirectPaymentInvoice

    @staticmethod
    def instance_to_values(instance: models.DirectPaymentInvoice) -> dict:  # type: ignore[type-var] # Type argument "DirectPaymentInvoice" of "BaseRepository" must be a subtype of "Instance"
        as_dict = dataclasses.asdict(instance)
        # these keys are set by the db so do not let them be inserted or updated
        for key in ["id", "created_at"]:
            _ = as_dict.pop(key, None)

        # special case process
        as_dict["created_by_process"] = as_dict["created_by_process"].value
        if as_dict.get("bills_allocated_by_process") is not None:
            as_dict["bills_allocated_by_process"] = as_dict[
                "bills_allocated_by_process"
            ].value
        return as_dict

    @staticmethod
    def table_columns() -> tuple[sa.Column, ...]:
        # fmt: off
        return (
            sa.Column("id", sa.BigInteger, autoincrement=True, primary_key=True, comment="Unique internal id."),
            sa.Column("uuid", UUID(), nullable=False, unique=True, default=lambda: str(uuid.uuid4()), comment="Unique external id. UUID4 format."),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp(), comment="The time at which this record was created."),
            sa.Column("reimbursement_organization_settings_id", sa.Integer, nullable=False, comment="ID of the reimbursement organisation settings."),
            sa.Column("bill_creation_cutoff_start_at", sa.DateTime, nullable=False, comment="Start time (inclusive) of the bill sweep-in time window. (UTC)"),
            sa.Column("bill_creation_cutoff_end_at", sa.DateTime, nullable=False, comment="End time (inclusive) of the bill sweep-in time window. (UTC)"),
            sa.Column("created_by_process", sa.String(length=255), nullable=False, comment="The process that created the invoice"),
            sa.Column("created_by_user_id", sa.Integer, nullable=True, comment="User id that created the record (if creation was via admin)"),
            sa.Column("bills_allocated_at", sa.DateTime, nullable=True, comment="The time at which bills were allocated to this invoice."),
            sa.Column("bills_allocated_by_process", sa.String(length=255), nullable=True, comment="The process that allocated bills to the invoice."),
            sa.Column("voided_at", sa.DateTime, nullable=True, comment="The time at which this invoice was voided.(UTC). Used for soft delete."),
            sa.Column("voided_by_user_id", sa.Integer, nullable=True, comment="User_id that voided the record (if the record was voided)"),
            sa.Column("report_generated_at", sa.DateTime, nullable=True, comment="The time at which the report was generated. UTC"),
            sa.Column("report_generated_json", sa.Text, nullable=True, comment="The generated report stored in JSON format (unenforced by db)"),
            sa.Column("bill_allocated_by_user_id", sa.Integer, nullable=True, comment="User id that allocated the bills (if allocation was via admin)"),
        )
        # fmt: on

    @classmethod
    def identity_columns(cls) -> tuple[sa.Column, ...]:
        return (sa.Column("id", sa.BigInteger, primary_key=True),)

    @classmethod
    def deserialize(
        cls, row: Optional[Mapping[str, Any]]
    ) -> models.DirectPaymentInvoice | None:
        if row is None:
            return None

        row_data = dict(row)

        # Mysql stores the UUIDs as a string so translate it here.
        if isinstance(row_data.get("uuid"), str):
            row_data["uuid"] = uuid.UUID(row_data["uuid"])

        row_data["created_by_process"] = models.Process(row_data["created_by_process"])
        if row_data.get("bills_allocated_by_process") is not None:
            row_data["bills_allocated_by_process"] = models.Process(
                row_data["bills_allocated_by_process"]
            )

        # The db row may have more fields than the model (post migration for instance) - so protect against this.
        expected_fields = {field.name for field in dataclasses.fields(cls.model)}
        expected_data = {
            column_name: value
            for column_name, value in row_data.items()
            if column_name in expected_fields
        }
        return cls.model(**expected_data)

    def get_latest_invoice_by_reimbursement_organization_settings_id(
        self, reimbursement_organization_settings_id: int
    ) -> models.DirectPaymentInvoice | None:
        """
        :param reimbursement_organization_settings_id:
        :return: The record with the latest bill_creation_cutoff_end_at for this reimbursement_organization_settings_id.
                 None if no records found.
        """
        query = """
                    SELECT *
                    FROM direct_payment_invoice
                    WHERE
                    reimbursement_organization_settings_id = :reimbursement_organization_settings_id 
                    ORDER BY bill_creation_cutoff_end_at DESC
                    LIMIT 1
                """
        execute = self.session.execute(
            query,
            {
                "reimbursement_organization_settings_id": reimbursement_organization_settings_id,
            },
        )
        result = execute.fetchone()
        to_return = self.deserialize(result) if result else None
        return to_return

    def get_org_level_invoice_report_data_query(self) -> Query:
        query = """
                SELECT
                    SHA2(CONCAT(SUBSTRING_INDEX(SUBSTRING_INDEX(report_generated_json, '"organisation_id": ', -1), ',', 1), bill_creation_cutoff_start_at, bill_creation_cutoff_end_at), 256) AS id,
                    SUBSTRING_INDEX(SUBSTRING_INDEX(report_generated_json, '"organisation_name": "', -1), '",', 1) AS organization_name,
                    CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(report_generated_json, '"organisation_id": ', -1), ',', 1) AS UNSIGNED) AS organization_id,
                    GROUP_CONCAT(direct_payment_invoice.id) AS ros_invoice_ids,
                    SUM(CAST(REPLACE(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(report_generated_json, '"clinic_bill_amount": "', -1), '",', 1), '$', ''), ',', '') AS DECIMAL(10, 2))) AS total_medical_cost_in_dollars,
                    SUM(CAST(REPLACE(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(report_generated_json, '"pharmacy_bill_amount": "', -1), '",', 1), '$', ''), ',', '') AS DECIMAL(10, 2))) AS total_pharmacy_cost_in_dollars,
                    bill_creation_cutoff_start_at,
                    bill_creation_cutoff_end_at
                FROM direct_payment_invoice
                GROUP BY organization_name, organization_id, bill_creation_cutoff_start_at, bill_creation_cutoff_end_at
        """

        columns = [
            Column("id", String),
            Column("organization_name", String),
            Column("organization_id", String),
            Column("ros_invoice_ids", String),
            Column("total_medical_cost_in_dollars", DECIMAL),
            Column("total_pharmacy_cost_in_dollars", DECIMAL),
            Column("bill_creation_cutoff_start_at", DateTime),
            Column("bill_creation_cutoff_end_at", DateTime),
        ]

        text_query = text(query).columns(*columns)  # type: ignore[arg-type]

        aliased_query = alias(text_query, name="org_direct_payment_invoice_report")

        # Create and return a Query object
        return self.session.query(
            aliased_query.c.id,
            aliased_query.c.organization_name,
            aliased_query.c.organization_id,
            aliased_query.c.ros_invoice_ids,
            aliased_query.c.total_medical_cost_in_dollars,
            aliased_query.c.total_pharmacy_cost_in_dollars,
            aliased_query.c.bill_creation_cutoff_start_at,
            aliased_query.c.bill_creation_cutoff_end_at,
        )

    def get_org_level_invoice_report_count_query(self) -> ResultProxy:
        query = """
            SELECT COUNT(*)
            FROM (
                SELECT 
                CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(report_generated_json, '"organisation_id": ', -1), ',', 1) AS UNSIGNED) AS organization_id,
                bill_creation_cutoff_start_at,
                bill_creation_cutoff_end_at
                FROM direct_payment_invoice
                GROUP BY organization_id, bill_creation_cutoff_start_at, bill_creation_cutoff_end_at
            ) AS subquery
        """

        return self.session.execute(query)
