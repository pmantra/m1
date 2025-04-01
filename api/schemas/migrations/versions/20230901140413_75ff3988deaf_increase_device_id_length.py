"""increase device_id length

Revision ID: 75ff3988deaf
Revises: dcb5c795c7c4
Create Date: 2023-09-01 14:04:13.417326+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "75ff3988deaf"
down_revision = "dcb5c795c7c4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `device`
        MODIFY COLUMN `device_id` VARCHAR(191) NOT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `device`
        MODIFY COLUMN `device_id` VARCHAR(80) NOT NULL;
        """
    )
