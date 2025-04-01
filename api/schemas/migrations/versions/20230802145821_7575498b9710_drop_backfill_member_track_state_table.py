"""drop_backfill_member_track_state_table

Revision ID: 7575498b9710
Revises: 38cb963f690a
Create Date: 2023-08-02 14:58:21.008893+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7575498b9710"
down_revision = "38cb963f690a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `backfill_member_track_state`
    """
    )


def downgrade():
    pass
