"""add reimbursement report columns

Revision ID: afdf8b97ee7a
Revises: 05aaf9925e87
Create Date: 2023-05-04 17:23:47.485905+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "afdf8b97ee7a"
down_revision = "05aaf9925e87"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "wallet_client_report_reimbursements",
        sa.Column("peakone_sent_date", sa.Date),
    )


def downgrade():
    op.drop_column("wallet_client_report_reimbursements", "peakone_sent_date")
