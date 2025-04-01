"""Add payments customer id to wallet

Revision ID: f2eeec063de9
Revises: cc954a6ef115
Create Date: 2023-06-30 19:47:22.805534+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2eeec063de9"
down_revision = "cc954a6ef115"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_wallet",
        sa.Column("payments_customer_id", sa.CHAR(36), nullable=True, unique=True),
    )


def downgrade():
    op.drop_column("reimbursement_wallet", "payments_customer_id")
