"""employer_health_plan_cost_sharing_add_tier2_percent_column

Revision ID: e1f6523d9396
Revises: 3707032583f6
Create Date: 2024-10-07 15:39:09.636132+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e1f6523d9396"
down_revision = "3707032583f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        ADD COLUMN `second_tier_percent` decimal(5,2) DEFAULT NULL AFTER percent,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        DROP COLUMN `second_tier_percent`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
