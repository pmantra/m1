"""Remove title and subtitle columns from reimbursement request category table

Revision ID: ae9bf1ee0d8b
Revises: c24241a5dd26
Create Date: 2023-02-28 18:50:36.102452+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ae9bf1ee0d8b"
down_revision = "c24241a5dd26"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("reimbursement_request_category", "title")
    op.drop_column(
        "reimbursement_request_category",
        "subtitle",
    )


def downgrade():
    op.add_column(
        "reimbursement_request_category",
        sa.Column("title", sa.VARCHAR(150), nullable=False),
    )

    op.add_column(
        "reimbursement_request_category",
        sa.Column("subtitle", sa.VARCHAR(150), nullable=True),
    )
