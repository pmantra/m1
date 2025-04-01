"""Add Alegeus transaction table

Revision ID: 1a2340ec21dd
Revises: 70feec76144d
Create Date: 2022-08-22 13:43:01.753752+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a2340ec21dd"
down_revision = "70feec76144d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_transaction",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_request_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request.id"),
        ),
        sa.Column(
            "alegeus_transaction_key", sa.VARCHAR(64), nullable=False, unique=True
        ),
        sa.Column("alegeus_plan_id", sa.VARCHAR(50), nullable=False),
        sa.Column("date", sa.DateTime, default=None),
        sa.Column("amount", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("description", sa.VARCHAR(255), nullable=True),
        sa.Column("status", sa.VARCHAR(15), nullable=True),
        sa.Column("service_start_date", sa.DateTime, default=None),
        sa.Column("service_end_date", sa.DateTime, default=None),
        sa.Column("settlement_date", sa.Date, default=None),
        sa.Column("sequence_number", sa.Integer, default=None),
    )


def downgrade():
    op.drop_table("reimbursement_transaction")
