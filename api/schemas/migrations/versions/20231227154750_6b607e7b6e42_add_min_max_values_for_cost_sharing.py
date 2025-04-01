"""add_min_max_values_for_cost_sharing

Revision ID: 6b607e7b6e42
Revises: ab97611e593f
Create Date: 2023-12-27 15:47:50.207029+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6b607e7b6e42"
down_revision = "ab97611e593f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        CHANGE COLUMN `cost_sharing_type` `cost_sharing_type` enum('COPAY','COINSURANCE', 'COINSURANCE_MIN', 'COINSURANCE_MAX') NOT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        CHANGE COLUMN `cost_sharing_type` `cost_sharing_type` enum('COPAY','COINSURANCE') NOT NULL;
        """
    )
