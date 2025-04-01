"""Create reimbursement_wallet_plan_hdhp table

Revision ID: 0b8316ce0ab9
Revises: 8b5d9559c983
Create Date: 2021-08-25 19:27:14.345744+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0b8316ce0ab9"
down_revision = "8b5d9559c983"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_wallet_plan_hdhp",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_plan_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_plan.id"),
        ),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
        ),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
    )


def downgrade():
    op.drop_table("reimbursement_wallet_plan_hdhp")
