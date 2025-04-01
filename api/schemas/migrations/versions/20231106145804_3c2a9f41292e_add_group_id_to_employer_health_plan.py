"""add_group_id_to_employer_health_plan

Revision ID: 3c2a9f41292e
Revises: 7636520812ef
Create Date: 2023-11-06 14:58:04.856161+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3c2a9f41292e"
down_revision = "7636520812ef"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `group_id` varchar(36) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `group_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
