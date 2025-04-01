"""update_refund_0_hours_cancellation_policy

Revision ID: ebc2b742e7fa
Revises: d7d565f56da8
Create Date: 2023-06-13 05:08:33.418898+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ebc2b742e7fa"
down_revision = "d7d565f56da8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ UPDATE cancellation_policy 
        SET refund_0_hours = 0 WHERE refund_0_hours IS NULL;"""
    )


def downgrade():
    pass
