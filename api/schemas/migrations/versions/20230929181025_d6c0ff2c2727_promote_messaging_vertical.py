"""promote_messaging_flags

Revision ID: d6c0ff2c2727
Revises: e48932a03177
Create Date: 2023-09-28 21:11:50.959365+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "d6c0ff2c2727"
down_revision = "e48932a03177"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `vertical`
        ADD COLUMN `promote_messaging` bool DEFAULT FALSE,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `vertical`
        DROP COLUMN `promote_messaging`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
