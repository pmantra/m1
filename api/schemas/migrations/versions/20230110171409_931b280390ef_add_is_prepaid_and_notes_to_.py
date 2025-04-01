"""add is_prepaid column to reimbursement_request table, add notes and remove is_prepaid columns
from reimbursement_transaction

Revision ID: 931b280390ef
Revises: 095c8a6dfa32
Create Date: 2023-01-10 17:14:09.746179+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "931b280390ef"
down_revision = "095c8a6dfa32"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_request",
        sa.Column("is_prepaid", sa.Boolean, nullable=True, default=False),
    )
    op.add_column("reimbursement_transaction", sa.Column("notes", sa.Text()))
    op.drop_column("reimbursement_transaction", "is_prepaid")


def downgrade():
    op.drop_column("reimbursement_request", "is_prepaid")
    op.drop_column("reimbursement_transaction", "notes")
    op.add_column(
        "reimbursement_transaction",
        sa.Column("is_prepaid", sa.Boolean, nullable=True, default=False),
    )
