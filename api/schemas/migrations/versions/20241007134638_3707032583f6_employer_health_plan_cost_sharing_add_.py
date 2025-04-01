"""employer_health_plan_cost_sharing_add_tier2_columns

Revision ID: 3707032583f6
Revises: 873b5f882e66
Create Date: 2024-10-07 13:46:38.410519+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "3707032583f6"
down_revision = "873b5f882e66"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        ADD COLUMN `second_tier_absolute_amount` int(11) DEFAULT NULL AFTER absolute_amount,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        DROP COLUMN `second_tier_absolute_amount`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
