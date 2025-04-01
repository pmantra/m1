"""Remove redundant unique constraint

Revision ID: 88b5b59b4150
Revises: e09d8a61308f
Create Date: 2023-03-15 18:37:48.600468+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "88b5b59b4150"
down_revision = "e09d8a61308f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "reimbursement_request_id",
        "wallet_client_report_reimbursements",
        type_="unique",
    )


def downgrade():
    op.create_unique_constraint(
        "reimbursement_request_id",
        "wallet_client_report_reimbursements",
        ["reimbursement_request_id"],
    )
