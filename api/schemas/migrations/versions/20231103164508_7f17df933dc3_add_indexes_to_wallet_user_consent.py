"""Add indexes to wallet user consent

Revision ID: 7f17df933dc3
Revises: 1ab286dd7488
Create Date: 2023-11-03 16:45:08.721013+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7f17df933dc3"
down_revision = "1ab286dd7488"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("idx_consent_giver_id", "wallet_user_consent", ["consent_giver_id"])
    op.create_index(
        "idx_consent_recipient_id", "wallet_user_consent", ["consent_recipient_id"]
    )
    op.create_index(
        "idx_reimbursement_wallet_id",
        "wallet_user_consent",
        ["reimbursement_wallet_id"],
    )


def downgrade():
    op.drop_index("idx_consent_giver_id", table_name="wallet_user_consent")
    op.drop_index("idx_consent_recipient_id", table_name="wallet_user_consent")
    op.drop_index("idx_reimbursement_wallet_id", table_name="wallet_user_consent")
