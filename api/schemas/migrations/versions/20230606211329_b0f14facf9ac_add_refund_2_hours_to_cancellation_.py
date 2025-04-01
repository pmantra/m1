"""add_refund_2_hours_to_cancellation_policy

Revision ID: b0f14facf9ac
Revises: f674e411821c
Create Date: 2023-06-06 21:13:29.438984+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b0f14facf9ac"
down_revision = "f674e411821c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ ALTER TABLE `cancellation_policy` 
        ADD COLUMN `refund_2_hours` int(11) DEFAULT NULL, 
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )


def downgrade():
    op.execute(
        """ ALTER TABLE `cancellation_policy` 
        DROP COLUMN `refund_2_hours`, 
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )
