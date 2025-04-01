"""update_refund_2_hours_cancellation_policy

Revision ID: 0da44cfc80ce
Revises: b0f14facf9ac
Create Date: 2023-06-07 03:41:23.206400+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0da44cfc80ce"
down_revision = "b0f14facf9ac"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ UPDATE cancellation_policy 
        SET refund_2_hours = 0 WHERE refund_2_hours IS NULL;"""
    )


def downgrade():
    pass
