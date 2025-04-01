"""create-fee-schedule-storage

Revision ID: 41efe3e1bcb6
Revises: ec6b6667de7a
Create Date: 2023-03-30 16:44:07.963380+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import DECIMAL

revision = "41efe3e1bcb6"
down_revision = "ec6b6667de7a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fee_schedule",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String(191), nullable=False, unique=True),
        sa.Column("deleted_at", sa.DateTime, default=None, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "fee_schedule_global_procedures",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "fee_schedule_id",
            sa.BigInteger,
            sa.ForeignKey("fee_schedule.id"),
            nullable=False,
        ),
        sa.Column(
            "reimbursement_wallet_global_procedures_id",
            sa.BigInteger,
            nullable=False,
        ),
        sa.Column("cost", DECIMAL(precision=8, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )
    op.create_unique_constraint(
        "fee_schedule_global_procedures_uq_1",
        "fee_schedule_global_procedures",
        ["fee_schedule_id", "reimbursement_wallet_global_procedures_id"],
    )


def downgrade():
    op.drop_table("fee_schedule_global_procedures")
    op.drop_table("fee_schedule")
