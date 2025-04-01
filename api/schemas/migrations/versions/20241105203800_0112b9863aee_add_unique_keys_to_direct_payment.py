"""add_unique_keys_to_direct_payment

Revision ID: 0112b9863aee
Revises: 2a4b2550d1f0
Create Date: 2024-11-05 20:38:00.210575+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0112b9863aee"
down_revision = "2a4b2550d1f0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `direct_payment_invoice`
        ADD UNIQUE `uk_ros_id_and_bill_creation_cutoff_start_at` (`reimbursement_organization_settings_id`, `bill_creation_cutoff_start_at`),
        ADD UNIQUE `uk_ros_id_and_bill_creation_cutoff_end_at` (`reimbursement_organization_settings_id`, `bill_creation_cutoff_end_at`),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `direct_payment_invoice`
        DROP INDEX `uk_ros_id_and_bill_creation_cutoff_start_at`,
        DROP INDEX `uk_ros_id_and_bill_creation_cutoff_end_at`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
