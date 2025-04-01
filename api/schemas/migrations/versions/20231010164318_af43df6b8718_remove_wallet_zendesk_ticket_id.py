"""Remove Wallet Zendesk_ticket_id

Revision ID: af43df6b8718
Revises: a6443b73f945
Create Date: 2023-10-10 16:43:18.062275+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "af43df6b8718"
down_revision = "a6443b73f945"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_wallet`
        DROP COLUMN `zendesk_ticket_id`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_wallet` 
        ADD COLUMN `zendesk_ticket_id` bigint(20) DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
