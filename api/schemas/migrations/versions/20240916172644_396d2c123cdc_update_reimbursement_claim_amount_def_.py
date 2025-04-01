"""update-reimbursement-claim-amount-def-for-rounding-bug

Revision ID: 396d2c123cdc
Revises: 52bdff1dca8f
Create Date: 2024-09-16 17:26:44.744815+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "396d2c123cdc"
down_revision = "52bdff1dca8f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_claim`
        MODIFY COLUMN `amount` decimal(8,2) DEFAULT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_claim`
        MODIFY COLUMN `amount` decimal(10,0) DEFAULT NULL;
        """
    )
