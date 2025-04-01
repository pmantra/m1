"""update_reschedule_history

Revision ID: bd7a33f2b109
Revises: c67f1e06e825
Create Date: 2023-09-05 19:51:10.135442+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "bd7a33f2b109"
down_revision = "c67f1e06e825"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reschedule_history`
        ADD COLUMN `id` int(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
        ALGORITHM=INPLACE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reschedule_history`
        DROP PRIMARY KEY,
        DROP COLUMN `id`;
        """
    )
