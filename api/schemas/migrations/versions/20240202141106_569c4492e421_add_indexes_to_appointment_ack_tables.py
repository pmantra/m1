"""add_indexes_to_appointment_ack_tables

Revision ID: 569c4492e421
Revises: f2b1dbb00734
Create Date: 2024-02-02 14:11:06.604310+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "569c4492e421"
down_revision = "c188d969ccb1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `practitioner_appointment_ack`
        ADD INDEX `idx_phone_number` (phone_number), 
        ADD INDEX `idx_is_acked` (is_acked), 
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """ 
        ALTER TABLE `practitioner_appointment_ack` 
        DROP INDEX `idx_is_acked`, 
        DROP INDEX `idx_phone_number`, 
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
