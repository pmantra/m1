"""reimbursement_wallet_users add created_at and modified_at

Revision ID: 47c01442925e
Revises: dca2b5b66c01
Create Date: 2023-06-14 22:55:08.640750+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "47c01442925e"
down_revision = "dca2b5b66c01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_wallet_users",
        sa.Column("created_at", sa.DateTime),
    )
    op.add_column(
        "reimbursement_wallet_users",
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_column("reimbursement_wallet_users", "created_at")
    op.drop_column("reimbursement_wallet_users", "modified_at")
