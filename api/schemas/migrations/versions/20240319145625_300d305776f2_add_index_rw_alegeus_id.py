"""add_index_rw_alegeus_id

Revision ID: 300d305776f2
Revises: ab02eff69511
Create Date: 2024-03-19 14:56:25.292976+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "300d305776f2"
down_revision = "7783ec40c780"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_wallet`
        ADD INDEX `idx_alegeus_id` (alegeus_id),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """ 
        ALTER TABLE `reimbursement_wallet` 
        DROP INDEX `idx_alegeus_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
