"""add_modified_at_column

Revision ID: ba3bae761b2b
Revises: 3ab107b77578
Create Date: 2023-09-13 17:43:33.238553+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ba3bae761b2b"
down_revision = "3ab107b77578"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reschedule_history`
        ADD COLUMN `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reschedule_history`
        DROP COLUMN `modified_at`,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
