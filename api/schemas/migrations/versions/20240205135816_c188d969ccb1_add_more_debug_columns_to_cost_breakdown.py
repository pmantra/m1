"""add_more_debug_columns_to_cost_breakdown

Revision ID: c188d969ccb1
Revises: c5acaaa37dc0
Create Date: 2024-02-05 13:58:16.849326+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c188d969ccb1"
down_revision = "c5acaaa37dc0"
branch_labels = None
depends_on = None


def upgrade():
    # Add a new ID field as the primary key
    op.execute(
        """
        ALTER TABLE cost_breakdown
        ADD COLUMN cost_breakdown_type enum('FIRST_DOLLAR_COVERAGE','HDHP', 'DEDUCTIBLE_ACCUMULATION') DEFAULT NULL after `amount_type`,
        ADD COLUMN member_id bigint(20) DEFAULT NULL after `wallet_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE cost_breakdown 
        DROP COLUMN cost_breakdown_type,
        DROP COLUMN member_id,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
