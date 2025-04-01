"""add_embedded_flags_to_employer_health_plan

Revision ID: 6bd2273378af
Revises: 961875048a2b
Create Date: 2023-11-27 20:41:21.007735+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6bd2273378af"
down_revision = "961875048a2b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `is_embedded`,
        ADD COLUMN `is_oop_embedded` tinyint(1) NOT NULL DEFAULT 0 after `fam_oop_max_limit`,
        ADD COLUMN `is_deductible_embedded` tinyint(1) NOT NULL DEFAULT 0 after `fam_deductible_limit`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `is_embedded` tinyint(1) NOT NULL DEFAULT 0 after `fam_oop_max_limit`,
        DROP COLUMN `is_oop_embedded`,
        DROP COLUMN `is_deductible_embedded`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
