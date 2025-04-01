"""add_qualified_for_optout_to_member_track

Revision ID: 0b5bc784a6a3
Revises: 0e04afa08f7c
Create Date: 2023-08-16 14:34:27.019874+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0b5bc784a6a3"
down_revision = "0e04afa08f7c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_track`
        ADD COLUMN `qualified_for_optout` bool DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_track`
        DROP COLUMN `qualified_for_optout`,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
