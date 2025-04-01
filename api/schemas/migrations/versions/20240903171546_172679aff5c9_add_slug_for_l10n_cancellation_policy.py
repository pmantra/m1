"""add slug for l10n cancellation_policy

Revision ID: 172679aff5c9
Revises: 0bfca93d4c21
Create Date: 2024-09-03 17:15:46.932131+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "172679aff5c9"
down_revision = "0bfca93d4c21"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `cancellation_policy`
        ADD COLUMN `slug` VARCHAR(128) DEFAULT NULL,
        ADD UNIQUE KEY `slug_uq_1` (`slug`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `cancellation_policy`
        DROP COLUMN `slug`,
        DROP KEY `slug_uq_1`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
