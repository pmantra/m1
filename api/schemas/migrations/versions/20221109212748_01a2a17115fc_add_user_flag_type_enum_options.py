"""add-user-flag-type-enum-options

Revision ID: 01a2a17115fc
Revises: 30179a5d81cf
Create Date: 2022-11-09 21:27:48.452922+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "01a2a17115fc"
down_revision = "30179a5d81cf"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `user_flag` MODIFY `type` enum('NONE', 'LOW_RISK', 'MEDIUM_RISK', 'HIGH_RISK') NOT NULL;
    """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `user_flag` MODIFY `type` enum('HIGH_RISK') NOT NULL;
    """
    )
