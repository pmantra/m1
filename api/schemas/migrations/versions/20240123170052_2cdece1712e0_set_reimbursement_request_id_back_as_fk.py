"""set_reimbursement_request_id_back_as_fk

Revision ID: 2cdece1712e0
Revises: da10bf948a17
Create Date: 2024-01-23 17:00:52.702491+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2cdece1712e0"
down_revision = "da10bf948a17"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE wallet_client_report_reimbursements "
        "ADD CONSTRAINT wallet_client_report_reimbursements_ibfk_1 "
        "FOREIGN KEY (reimbursement_request_id) REFERENCES reimbursement_request (id), "
        "ALGORITHM=COPY, LOCK=SHARED;"
    )


def downgrade():
    op.execute(
        "ALTER TABLE wallet_client_report_reimbursements "
        "DROP FOREIGN KEY wallet_client_report_reimbursements_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE;"
    )
