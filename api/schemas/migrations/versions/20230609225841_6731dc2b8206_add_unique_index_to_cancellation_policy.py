"""add_unique_index_to_cancellation_policy

Revision ID: 6731dc2b8206
Revises: 83e5e71bcdfd
Create Date: 2023-06-09 22:58:41.514595+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6731dc2b8206"
down_revision = "83e5e71bcdfd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `cancellation_policy`
            ADD UNIQUE INDEX `uidx_name_cancellation_policy` (name), 
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `cancellation_policy`
            DROP INDEX `uidx_name_cancellation_policy`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
