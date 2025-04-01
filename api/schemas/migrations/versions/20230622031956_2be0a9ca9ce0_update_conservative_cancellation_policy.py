"""update-conservative-cancellation-policy

Revision ID: 2be0a9ca9ce0
Revises: 3fed0805b34e
Create Date: 2023-06-22 03:19:56.700948+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2be0a9ca9ce0"
down_revision = "3fed0805b34e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ UPDATE cancellation_policy 
        SET refund_0_hours = 50, refund_2_hours = 100, refund_6_hours = 100, refund_12_hours = 100, refund_24_hours = 100, refund_48_hours = 100 
        WHERE name = 'conservative';"""
    )


def downgrade():
    pass
