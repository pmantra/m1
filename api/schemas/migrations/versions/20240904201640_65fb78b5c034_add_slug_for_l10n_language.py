"""add slug for l10n language

Revision ID: 65fb78b5c034
Revises: 9a1c75534a06
Create Date: 2024-09-04 20:16:40.549232+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "65fb78b5c034"
down_revision = "9a1c75534a06"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `language`
        ADD COLUMN `slug` VARCHAR(128) DEFAULT NULL,
        ADD UNIQUE KEY `slug_uq_1` (`slug`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `language`
        DROP COLUMN `slug`,
        DROP KEY `slug_uq_1`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
