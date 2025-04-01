"""create cost breakdown data model

Revision ID: ad0f786758da
Revises: ff8fd19f6287
Create Date: 2023-06-13 19:19:38.653289+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ad0f786758da"
down_revision = "ff8fd19f6287"
branch_labels = None
depends_on = None


def upgrade():
    class AmountType(enum.Enum):
        INDIVIDUAL = "INDIVIDUAL"
        FAMILY = "FAMILY"

    op.create_table(
        "cost_breakdown",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "wallet_id",
            sa.BigInteger,
            nullable=False,
        ),
        sa.Column(
            "treatment_procedure_uuid",
            sa.String(36),
            nullable=True,
        ),
        sa.Column("total_member_responsibility", sa.Integer, nullable=False),
        sa.Column("total_employer_responsibility", sa.Integer, nullable=False),
        sa.Column("beginning_wallet_balance", sa.Integer, nullable=False),
        sa.Column("ending_wallet_balance", sa.Integer, nullable=False),
        sa.Column("deductible", sa.Integer, default=0),
        sa.Column("coinsurance", sa.Integer, default=0),
        sa.Column("copay", sa.Integer, default=0),
        sa.Column("overage_amount", sa.Integer, default=0),
        sa.Column("oop_remaining", sa.Integer, default=0),
        sa.Column(
            "amount_type",
            sa.Enum(AmountType),
            default=AmountType.INDIVIDUAL,
            nullable=False,
        ),
        sa.Column(
            "rte_transaction_id",
            sa.BigInteger,
            sa.ForeignKey("rte_transaction.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade():
    op.drop_table("cost_breakdown")
