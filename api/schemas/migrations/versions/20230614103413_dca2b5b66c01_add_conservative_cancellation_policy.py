"""add_conservative_cancellation_policy

Revision ID: dca2b5b66c01
Revises: 086cf3b300fb
Create Date: 2023-06-14 10:34:13.119067+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "dca2b5b66c01"
down_revision = "086cf3b300fb"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """INSERT INTO cancellation_policy (name, refund_0_hours, refund_2_hours, refund_6_hours, refund_12_hours, refund_24_hours, refund_48_hours, created_at, modified_at)
        VALUES ('conservative', 0, 0, 0, 0, 100, 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP); """
    )


def downgrade():
    op.execute("""DELETE FROM cancellation_policy WHERE name = 'conservative'; """)
