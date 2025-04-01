"""remove_fk_from_wallet_client_report_reimbursements

Revision ID: 2e214377dada
Revises: 2f4ebc2c1a9b
Create Date: 2024-01-23 11:24:47.729525+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2e214377dada"
down_revision = "2f4ebc2c1a9b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE wallet_client_report_reimbursements "
        "DROP FOREIGN KEY wallet_client_report_reimbursements_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE wallet_client_report_reimbursements "
        "ADD CONSTRAINT wallet_client_report_reimbursements_ibfk_1 "
        "FOREIGN KEY (reimbursement_request_id) REFERENCES reimbursement_request (id);"
    )
