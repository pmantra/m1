"""Contentful migration field on resources table

Revision ID: d71ded921b03
Revises: e7b69051607d
Create Date: 2023-01-03 19:12:10.104228+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d71ded921b03"
down_revision = "e7b69051607d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE `resource` ADD COLUMN `contentful_status` enum('NOT_STARTED', 'IN_PROGRESS', 'LIVE') NOT NULL DEFAULT 'NOT_STARTED';
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE `resource` DROP COLUMN `contentful_status`;
    """
    )
