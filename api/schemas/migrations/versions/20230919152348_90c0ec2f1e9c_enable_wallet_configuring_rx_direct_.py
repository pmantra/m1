"""enable wallet configuring rx direct payment

Revision ID: 90c0ec2f1e9c
Revises: fd891c55b949
Create Date: 2023-09-19 15:23:48.704736+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "90c0ec2f1e9c"
down_revision = "fd891c55b949"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings`
        ADD COLUMN `rx_direct_payment_enabled` tinyint(1) NOT NULL after `direct_payment_enabled`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings`
        DROP COLUMN `rx_direct_payment_enabled`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
