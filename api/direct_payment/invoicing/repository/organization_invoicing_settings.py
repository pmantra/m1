from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Mapping, Optional

import ddtrace
import sqlalchemy as sa

from direct_payment.invoicing import models
from direct_payment.invoicing.repository.common import UUID
from storage.repository import base
from utils.log import logger

log = logger(__name__)

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class OrganizationInvoicingSettingsRepository(
    base.BaseRepository[models.OrganizationInvoicingSettings]  # type: ignore[type-var]
):
    model = models.OrganizationInvoicingSettings

    @staticmethod
    def instance_to_values(instance: models.OrganizationInvoicingSettings) -> dict:  # type: ignore[type-var] # Type argument "OrganizationInvoicingSettings" of "BaseRepository" must be a subtype of "Instance"
        as_dict = dataclasses.asdict(instance)
        # these keys are set by the db so do not let them be inserted or updated
        for key in ["id", "created_at", "updated_at"]:
            _ = as_dict.pop(key, None)
        return as_dict

    @staticmethod
    def table_columns() -> tuple[sa.Column, ...]:
        # fmt: off
        return (
            sa.Column("id", sa.BigInteger, autoincrement=True, primary_key=True, comment="Unique internal id."),
            sa.Column("uuid", UUID(), nullable=False, unique=True, default=lambda: str(uuid.uuid4()), comment="Unique external id. UUID4 format."),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp(), comment="The time at which this record was created."),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), comment="The time at which this record was updated."),
            sa.Column("organization_id", sa.Integer, nullable=False, comment="ID of the org."),
            sa.Column("created_by_user_id", sa.Integer, nullable=False, comment="user_id that created the record"),
            sa.Column("updated_by_user_id", sa.Integer, nullable=False, comment="user_id that updated the record"),
            sa.Column("invoicing_active_at", sa.DateTime, nullable=True, comment="The date at which the employer activated invoice based billing."),
            sa.Column("invoice_cadence", sa.String(13), nullable=True, comment="Invoice generation cadence in CRON format. application will ignore hh mm."),
            sa.Column("bill_processing_delay_days", sa.SmallInteger, nullable=False, default=14, comment="Bills will be processed bill_processing_delay_days after bill creation."),
            sa.Column("bill_cutoff_at_buffer_days", sa.SmallInteger, nullable=False, default=2, comment="The cutoff offset in days from the current date for the latest bill creation date. "),
        )
        # fmt: on

    @classmethod
    def identity_columns(cls) -> tuple[sa.Column, ...]:
        return (sa.Column("id", sa.BigInteger, primary_key=True),)

    @classmethod
    def deserialize(
        cls, row: Optional[Mapping[str, Any]]
    ) -> models.OrganizationInvoicingSettings | None:
        if row is None:
            return None

        row_data = dict(row)
        # Mysql stores the UUIDs as a string so translate it here.
        if isinstance(row_data.get("uuid"), str):
            row_data["uuid"] = uuid.UUID(row_data["uuid"])

        # The db row may have more fields than the model (post migration for instance) - so protect against this.
        expected_fields = {field.name for field in dataclasses.fields(cls.model)}
        expected_data = {
            column_name: value
            for column_name, value in row_data.items()
            if column_name in expected_fields
        }
        return cls.model(**expected_data)

    @trace_wrapper
    def get_by_organization_id(
        self, *, organization_id: int
    ) -> models.OrganizationInvoicingSettings | None:  # type: ignore[arg-type]
        where = self.table.c.organization_id == organization_id
        result = self.execute_select(where=where, from_obj=self.from_obj)  # type: ignore[arg-type] # Argument "from_obj" to "execute_select" of "BaseRepository" has incompatible type "Optional[Selectable]"; expected "Selectable"
        row = result.first()
        return self.deserialize(row=row)

    @trace_wrapper
    def get_by_uuid(self, *, uuid: UUID) -> models.OrganizationInvoicingSettings | None:  # type: ignore[arg-type]
        where = self.table.c.uuid == uuid
        result = self.execute_select(where=where, from_obj=self.from_obj)  # type: ignore[arg-type] # Argument "from_obj" to "execute_select" of "BaseRepository" has incompatible type "Optional[Selectable]"; expected "Selectable"
        row = result.first()
        return self.deserialize(row=row)

    @trace_wrapper
    def delete_by_organization_id(self, *, organization_id: int) -> int:
        delete = self.table.delete(
            whereclause=self.table.c.organization_id == organization_id
        )
        result = self.session.execute(delete)
        if not self._is_in_uow:
            self.session.commit()
        affected: int = result.rowcount
        return affected

    @trace_wrapper
    def delete_by_uuid(self, *, uuid: uuid.UUID) -> int:
        delete = self.table.delete(whereclause=self.table.c.uuid == uuid)
        result = self.session.execute(delete)
        if not self._is_in_uow:
            self.session.commit()
        affected: int = result.rowcount
        return affected

    @trace_wrapper
    def get_by_payments_customer_id(
        self, *, payments_customer_id: int
    ) -> models.OrganizationInvoicingSettings | None:

        query = """
                SELECT o.*
                FROM organization_invoicing_settings o
                INNER JOIN reimbursement_organization_settings s ON o.organization_id = s.organization_id
                AND s.payments_customer_id = :payments_customer_id
        """
        results = self.session.execute(
            query,
            {"payments_customer_id": payments_customer_id},
        ).fetchall()
        if len(results) > 1:
            # reimbursement_org_settings table does not enforce a uniqueness constraint on payments_customer_id so
            # multiple results are allowed as long as it is the same org id.
            orgs = {r["organization_id"] for r in results}
            if len(orgs) > 1:
                raise ValueError(
                    f"Query returned multiple results for {payments_customer_id}"
                )
        to_return = self.deserialize(results[0]) if results else None
        return to_return

    @trace_wrapper
    def get_by_reimbursement_org_settings_id(
        self, *, reimbursement_organization_settings_id: int
    ) -> models.OrganizationInvoicingSettings | None:

        query = """
                    SELECT o.*
                    FROM organization_invoicing_settings o
                    INNER JOIN reimbursement_organization_settings r ON o.organization_id = r.organization_id
                    AND r.id = :reimbursement_organization_settings_id
            """
        results = self.session.execute(
            query,
            {
                "reimbursement_organization_settings_id": reimbursement_organization_settings_id
            },
        ).fetchone()
        to_return = self.deserialize(results) if results else None
        return to_return
