"""remove_rw_fk_oe

Revision ID: 5c5e8821c03d
Revises: 1b0bbe1e61cf
Create Date: 2025-02-07 14:51:26.438733+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5c5e8821c03d"
down_revision = "1b0bbe1e61cf"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE reimbursement_wallet "
        "DROP FOREIGN KEY reimbursement_wallet_ibfk_3, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute("DROP INDEX reimbursement_wallet_ibfk_3 ON reimbursement_wallet")
    op.execute(
        "CREATE INDEX reimbursement_wallet_ibfk_3 ON reimbursement_wallet(organization_employee_id)"
    )
    op.execute(
        "ALTER TABLE reimbursement_wallet "
        "ADD CONSTRAINT reimbursement_wallet_ibfk_3 "
        "FOREIGN KEY (organization_employee_id) REFERENCES organization_employee(id)"
    )
