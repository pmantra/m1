"""add slug for l10n need_category

Revision ID: d81769b17be7
Revises: a60aee1e0f4a
Create Date: 2024-09-03 17:14:50.117302+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d81769b17be7"
down_revision = "a60aee1e0f4a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `need_category`
        ADD COLUMN `slug` VARCHAR(128) DEFAULT NULL,
        ADD UNIQUE KEY `slug_uq_1` (`slug`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `need_category`
        DROP COLUMN `slug`,
        DROP KEY `slug_uq_1`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
