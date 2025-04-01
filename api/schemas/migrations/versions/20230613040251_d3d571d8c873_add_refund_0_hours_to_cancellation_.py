"""add_refund_0_hours_to_cancellation_policy

Revision ID: d3d571d8c873
Revises: e94548d562a7
Create Date: 2023-06-13 04:02:51.954715+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d3d571d8c873"
down_revision = "e94548d562a7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ ALTER TABLE `cancellation_policy` 
        ADD COLUMN `refund_0_hours` int(11) DEFAULT NULL, 
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )


def downgrade():
    op.execute(
        """ ALTER TABLE `cancellation_policy` 
        DROP COLUMN `refund_0_hours`, 
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )
