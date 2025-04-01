"""drop_backfill_credit_state_table

Revision ID: c54d46d01d82
Revises: 4a9cf0b567e2
Create Date: 2023-07-31 17:32:26.645015+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c54d46d01d82"
down_revision = "4a9cf0b567e2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `backfill_credit_state`
    """
    )


def downgrade():
    pass
