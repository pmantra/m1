"""Remove first_name, last_name, and phone number from debit card model

Revision ID: 8b190e8533df
Revises: bee4ba5684b5
Create Date: 2022-09-22 18:33:37.069678+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b190e8533df"
down_revision = "bee4ba5684b5"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("reimbursement_wallet_debit_card", "first_name")
    op.drop_column("reimbursement_wallet_debit_card", "last_name")
    op.drop_column("reimbursement_wallet_debit_card", "phone_number")


def downgrade():
    op.add_column(
        "reimbursement_wallet_debit_card",
        sa.Column("first_name", sa.String(255), nullable=False),
    )
    op.add_column(
        "reimbursement_wallet_debit_card",
        sa.Column("last_name", sa.String(255), nullable=False),
    )
    op.add_column(
        "reimbursement_wallet_debit_card",
        sa.Column("phone_number", sa.String(255), nullable=True),
    )
