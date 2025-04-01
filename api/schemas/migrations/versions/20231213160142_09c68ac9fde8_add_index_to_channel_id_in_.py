"""add index to channel_id field in reimbursement_wallet_users table

Revision ID: 09c68ac9fde8
Revises: 284a15d61d48
Create Date: 2023-12-13 16:01:42.139842+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "09c68ac9fde8"
down_revision = "284a15d61d48"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_channel_id", "reimbursement_wallet_users", ["channel_id"])


def downgrade():
    op.execute("SET SESSION foreign_key_checks = 0")
    op.drop_index("ix_channel_id", table_name="reimbursement_wallet_users")
    op.execute("SET SESSION foreign_key_checks = 1")
