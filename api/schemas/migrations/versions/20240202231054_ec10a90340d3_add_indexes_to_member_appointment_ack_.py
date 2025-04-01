"""add_indexes_to_member_appointment_ack_table

Revision ID: ec10a90340d3
Revises: 0a3d3275a24c
Create Date: 2024-02-02 23:10:54.064352+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ec10a90340d3"
down_revision = "460cde27a2be"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_appointment_ack`
        ADD INDEX `idx_phone_number` (phone_number), 
        ADD INDEX `idx_is_acked` (is_acked), 
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """ 
        ALTER TABLE `member_appointment_ack` 
        DROP INDEX `idx_is_acked`, 
        DROP INDEX `idx_phone_number`, 
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
