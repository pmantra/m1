"""add fully covered to member health plan table

Revision ID: c6a3c6796445
Revises: 7c02efcf741c
Create Date: 2023-09-12 14:00:58.883464+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c6a3c6796445"
down_revision = "7c02efcf741c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        ADD COLUMN `fully_covered` tinyint(1) DEFAULT '0' after `is_family_plan`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        DROP COLUMN `fully_covered`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
