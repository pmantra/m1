"""remove_pk_on_wallet_client_report_reimbursements

Revision ID: 7c35f37a173e
Revises: 2e214377dada
Create Date: 2024-01-23 14:22:19.869754+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7c35f37a173e"
down_revision = "2e214377dada"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the primary key constraint from reimbursement_request_id
    op.execute(
        "ALTER TABLE wallet_client_report_reimbursements DROP PRIMARY KEY, ALGORITHM=COPY, LOCK=SHARED;"
    )


def downgrade():
    op.execute(
        """
        -- Add the primary key constraint back to 'reimbursement_request_id'
        ALTER TABLE wallet_client_report_reimbursements
        ADD PRIMARY KEY (reimbursement_request_id),
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    )
