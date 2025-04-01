from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.util

from direct_payment.pharmacy.models.pharmacy_prescription import (
    PharmacyPrescription,
    PrescriptionStatus,
)
from storage.repository import base
from utils.data import JSONAlchemy


class PharmacyPrescriptionRepository(base.BaseRepository[PharmacyPrescription]):  # type: ignore[type-var] # Type argument "PharmacyPrescription" of "BaseRepository" must be a subtype of "Instance"
    model = PharmacyPrescription

    @classmethod
    def identity_columns(cls) -> tuple[sa.Column, ...]:
        return (
            sa.Column(
                "created_at",
                sa.TIMESTAMP,
                nullable=False,
                server_default=sa.FetchedValue(),
            ),
            sa.Column(
                "modified_at",
                sa.TIMESTAMP,
                nullable=False,
                server_default=sa.FetchedValue(),
                server_onupdate=sa.FetchedValue(for_update=True),
            ),
        )

    @staticmethod
    def table_columns() -> tuple[sqlalchemy.Column, ...]:
        return (
            sa.Column(
                "id",
                sa.Integer,
                primary_key=True,
                autoincrement=True,
                nullable=False,
            ),
            sa.Column("status", sa.Enum(PrescriptionStatus), nullable=False),
            sa.Column(
                "treatment_procedure_id",
                sa.BigInteger,
                sa.ForeignKey("treatment_procedure.id"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("user.id"),
                nullable=False,
            ),
            sa.Column(
                "reimbursement_request_id",
                sa.Integer,
                sa.ForeignKey("reimbursement_request.id"),
                nullable=True,
            ),
            sa.Column("maven_benefit_id", sa.String, nullable=True),
            sa.Column("user_benefit_id", sa.String, nullable=True),
            sa.Column("rx_unique_id", sa.String, nullable=False),
            sa.Column("amount_owed", sa.Integer, nullable=False),
            sa.Column("ncpdp_number", sa.String, nullable=False),
            sa.Column("ndc_number", sa.String, nullable=False),
            sa.Column("rx_name", sa.String, nullable=False),
            sa.Column("rx_description", sa.Text, nullable=False),
            sa.Column("rx_first_name", sa.String, nullable=False),
            sa.Column("rx_last_name", sa.String, nullable=False),
            sa.Column("rx_order_id", sa.String, nullable=False),
            sa.Column("rx_received_date", sa.DateTime, nullable=False),
            sa.Column("rx_filled_date", sa.DateTime, nullable=True),
            sa.Column("scheduled_ship_date", sa.DateTime, nullable=True),
            sa.Column("actual_ship_date", sa.DateTime, nullable=True),
            sa.Column("cancelled_date", sa.DateTime, nullable=True),
            sa.Column("scheduled_json", JSONAlchemy(sa.Text), nullable=True),
            sa.Column("shipped_json", JSONAlchemy(sa.Text), nullable=True),
            sa.Column("cancelled_json", JSONAlchemy(sa.Text), nullable=True),
            sa.Column("reimbursement_json", JSONAlchemy(sa.Text), nullable=True),
        )

    def get_by_rx_unique_id(
        self,
        rx_unique_id: str,
        status: PrescriptionStatus | None = None,
    ) -> PharmacyPrescription | None:
        """Get a PharmacyPrescription by rx_unique_id and optionally a status."""
        where = [self.table.c.rx_unique_id == rx_unique_id]
        if status:
            where.append(self.table.c.status == status)
        result = self.execute_select(where=sa.and_(*where))
        row = result.first()
        return self.deserialize(row=row)

    def get_by_reimbursement_request_ids(
        self, reimbursement_request_ids: list[str]
    ) -> list:
        where = [self.table.c.reimbursement_request_id.in_(reimbursement_request_ids)]
        result = self.execute_select(where=sa.and_(*where))
        return [self.deserialize(row) for row in result.fetchall()]

    def get_by_procedure_ids(self, procedure_ids: list[int]) -> list:
        where = [self.table.c.treatment_procedure_id.in_(procedure_ids)]
        result = self.execute_select(where=sa.and_(*where))
        return [self.deserialize(row) for row in result.fetchall()]

    def get_by_time_range(
        self, start_time: Optional[datetime], end_time: datetime
    ) -> list:
        """Get pharmacy prescriptions within time range [start_time, end_time]"""
        where = self.table.c.created_at.between(start_time, end_time)
        result = self.execute_select(where=where)
        return [self.deserialize(row) for row in result.fetchall()]
