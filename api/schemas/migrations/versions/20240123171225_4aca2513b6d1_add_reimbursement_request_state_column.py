"""add_reimbursement_request_state_column

Revision ID: 4aca2513b6d1
Revises: 2cdece1712e0
Create Date: 2024-01-23 17:12:25.953229+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4aca2513b6d1"
down_revision = "2cdece1712e0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        -- Add the new column 'reimbursement_request_state' with the default value 'APPROVED'
        ALTER TABLE wallet_client_report_reimbursements
        ADD COLUMN reimbursement_request_state ENUM(
            'NEW', 'PENDING', 'APPROVED', 'REIMBURSED', 'DENIED', 'FAILED', 'NEEDS_RECEIPT',
            'RECEIPT_SUBMITTED', 'INSUFFICIENT_RECEIPT', 'INELIGIBLE_EXPENSE', 'RESOLVED', 'REFUNDED'
        ) NOT NULL DEFAULT 'APPROVED',
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    )


def downgrade():
    op.execute(
        """
        -- Remove the 'reimbursement_request_state' column
        ALTER TABLE wallet_client_report_reimbursements
        DROP COLUMN reimbursement_request_state,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    )
