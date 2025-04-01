"""Create Reimbursement Exchange Rate Table

Revision ID: 6aa151532c8b
Revises: 357a5f84f53e
Create Date: 2022-07-19 15:07:06.600953+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6aa151532c8b"
down_revision = "357a5f84f53e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_request_exchange_rates",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_currency", sa.CHAR(3), nullable=False),
        sa.Column("target_currency", sa.CHAR(3), nullable=False),
        sa.Column("trading_date", sa.Date, nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=8, scale=2), nullable=False),
    )
    op.create_unique_constraint(
        constraint_name="uq_source_target_rate",
        table_name="reimbursement_request_exchange_rates",
        columns=["source_currency", "target_currency", "trading_date"],
    )


def downgrade():
    op.drop_table("reimbursement_request_exchange_rates")
