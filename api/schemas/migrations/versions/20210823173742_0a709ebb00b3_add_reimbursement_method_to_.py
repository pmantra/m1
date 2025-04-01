"""Add reimbursement_method to reimbursement_wallet table

Revision ID: 0a709ebb00b3
Revises: c110f6689cc8
Create Date: 2021-08-23 17:37:42.392085+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from wallet.models.constants import ReimbursementMethod

revision = "0a709ebb00b3"
down_revision = "c110f6689cc8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_wallet",
        sa.Column("reimbursement_method", sa.Enum(ReimbursementMethod)),
    )


def downgrade():
    op.drop_column("reimbursement_wallet", "reimbursement_method")
