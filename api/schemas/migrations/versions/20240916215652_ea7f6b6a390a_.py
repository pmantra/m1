"""

Revision ID: ea7f6b6a390a
Revises: b5a979514aec
Create Date: 2024-09-16 21:56:52.396982+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ea7f6b6a390a"
down_revision = "b5a979514aec"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_preferences` MODIFY COLUMN `created_at` datetime DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE `member_preferences` MODIFY COLUMN `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_preferences` MODIFY COLUMN `created_at` datetime DEFAULT NULL;
        ALTER TABLE `member_preferences` MODIFY COLUMN `modified_at` datetime DEFAULT NULL;
        """
    )
