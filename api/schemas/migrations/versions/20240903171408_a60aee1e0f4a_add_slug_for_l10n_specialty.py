"""add slug for l10n specialty

Revision ID: a60aee1e0f4a
Revises: 1d529b70f917
Create Date: 2024-09-03 17:14:08.841376+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a60aee1e0f4a"
down_revision = "1d529b70f917"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """       
        ALTER TABLE `specialty`
        ADD COLUMN `slug` VARCHAR(128) DEFAULT NULL,
        ADD UNIQUE KEY `slug_uq_1` (`slug`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `specialty`
        DROP COLUMN `slug`,
        DROP KEY `slug_uq_1`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
