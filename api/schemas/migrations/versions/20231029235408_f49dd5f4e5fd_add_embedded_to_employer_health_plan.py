"""add_embedded_to_employer_health_plan

Revision ID: f49dd5f4e5fd
Revises: ad792dd36510
Create Date: 2023-10-29 23:54:08.398963+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f49dd5f4e5fd"
down_revision = "ad792dd36510"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `is_embedded` tinyint(1) NOT NULL DEFAULT 0 after `fam_oop_max_limit`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `is_embedded`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
