"""Create reimbursement_account table

Revision ID: c110f6689cc8
Revises: f7ca34b5d45c
Create Date: 2021-08-13 17:37:27.716769+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c110f6689cc8"
down_revision = "f7ca34b5d45c"
branch_labels = None
depends_on = None


class ReimbursementAccountStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    PERMANENTLY_INACTIVE = "PERMANENTLY_INACTIVE"


class AlegeusAccountType(enum.Enum):
    HRA = "HRA"
    HR2 = "HR2"
    DTR = "DTR"
    HR4 = "HR4"
    HR3 = "HR3"
    HRX = "HRX"


def upgrade():
    op.create_table(
        "reimbursement_account",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
        ),
        sa.Column(
            "reimbursement_plan_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_plan.id"),
        ),
        sa.Column("status", sa.Enum(ReimbursementAccountStatus), nullable=True),
        sa.Column("alegeus_account_type", sa.Enum(AlegeusAccountType), nullable=True),
    )


def downgrade():
    op.drop_table("reimbursement_account")
