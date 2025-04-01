"""treatment_procedure

Revision ID: f674e411821c
Revises: 8479c3c5a8a0
Create Date: 2023-05-31 22:52:59.758115+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f674e411821c"
down_revision = "c91093fae227"
branch_labels = None
depends_on = None


def upgrade():
    class TreatmentProcedureStatus(enum.Enum):
        SCHEDULED = "SCHEDULED"
        COMPLETED = "COMPLETED"
        PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
        CANCELLED = "CANCELLED"

    op.create_table(
        "treatment_procedure",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("uuid", sa.String(36), unique=True, nullable=False),
        sa.Column("member_id", sa.BigInteger, nullable=False),
        sa.Column("reimbursement_wallet_id", sa.BigInteger, nullable=False),
        sa.Column(
            "reimbursement_request_category_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request_category.id"),
            nullable=False,
        ),
        sa.Column(
            "fee_schedule_id",
            sa.BigInteger,
            sa.ForeignKey("fee_schedule.id"),
            nullable=False,
        ),
        sa.Column(
            "reimbursement_wallet_global_procedures_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet_global_procedures.id"),
            nullable=False,
        ),
        sa.Column(
            "fertility_clinic_id",
            sa.BigInteger,
            sa.ForeignKey("fertility_clinic.id"),
            nullable=False,
        ),
        sa.Column(
            "fertility_clinic_location_id",
            sa.BigInteger,
            sa.ForeignKey("fertility_clinic_location.id"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("procedure_name", sa.String(191), nullable=False),
        sa.Column("cost", sa.Integer, nullable=False),
        sa.Column("status", sa.Enum(TreatmentProcedureStatus), nullable=False),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("cancelled_date", sa.DateTime, nullable=True),
        sa.Column("completed_date", sa.DateTime, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "modified_at",
            sa.TIMESTAMP,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("treatment_procedure")
