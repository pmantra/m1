"""

Revision ID: 915796353507
Revises: ea7f6b6a390a
Create Date: 2024-09-26 19:41:19.489986+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "915796353507"
down_revision = "ea7f6b6a390a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `preference` MODIFY COLUMN `created_at` datetime DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE `preference` MODIFY COLUMN `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `preference` MODIFY COLUMN `created_at` datetime DEFAULT NULL;
        ALTER TABLE `preference` MODIFY COLUMN `modified_at` datetime DEFAULT NULL;
        """
    )
