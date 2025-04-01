"""Add intended expense type to Wallet

Revision ID: 47e7bdea398d
Revises: 0675ec6f1f80
Create Date: 2023-05-12 20:01:45.649316+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.constants import ReimbursementRequestExpenseTypes

# revision identifiers, used by Alembic.
revision = "47e7bdea398d"
down_revision = "0675ec6f1f80"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_wallet",
        sa.Column(
            "primary_expense_type",
            sa.Enum(ReimbursementRequestExpenseTypes),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("reimbursement_wallet", "primary_expense_type")
