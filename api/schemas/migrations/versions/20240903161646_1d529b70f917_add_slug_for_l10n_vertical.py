"""add slugs for l10n

Revision ID: 1d529b70f917
Revises: fb4f2099a9a4
Create Date: 2024-09-03 20:16:46.825413+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "1d529b70f917"
down_revision = "c380fb384135"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `vertical`
        ADD COLUMN `slug` VARCHAR(128) DEFAULT NULL,
        ADD UNIQUE KEY `slug_uq_1` (`slug`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """                
        ALTER TABLE `vertical`
        DROP COLUMN `slug`,
        DROP KEY `slug_uq_1`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
