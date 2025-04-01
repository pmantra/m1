"""add-carrier-number-to-employer-health-plan-table

Revision ID: 6219ce1fefcf
Revises: 3c2a9f41292e
Create Date: 2023-11-06 18:02:57.002736+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6219ce1fefcf"
down_revision = "3c2a9f41292e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `carrier_number` VARCHAR(36) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `carrier_number`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
