"""remove_backfill_verification_state_table

Revision ID: 7c02efcf741c
Revises: f1b432a8061a
Create Date: 2023-09-12 14:01:51.540758+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7c02efcf741c"
down_revision = "f1b432a8061a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS maven.`backfill_verification_state`;
    """
    )


def downgrade():
    # backfill_verification_state is a temp table for backfill only,
    # at this time, no need to create it back again since the backfill is done
    pass
