"""promote_messaging_flags

Revision ID: e48932a03177
Revises: 0c006e9f0ba9
Create Date: 2023-09-28 21:11:50.959365+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e48932a03177"
down_revision = "0c006e9f0ba9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `need`
        ADD COLUMN `promote_messaging` bool DEFAULT FALSE,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `need`
        DROP COLUMN `promote_messaging`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
