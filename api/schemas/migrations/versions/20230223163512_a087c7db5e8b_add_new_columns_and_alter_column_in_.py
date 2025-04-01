"""Add new columns and alter column in reimbursement_request_category

Revision ID: a087c7db5e8b
Revises: 2ce9b50109ed
Create Date: 2023-02-23 16:35:12.666913+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a087c7db5e8b"
down_revision = "2ce9b50109ed"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_request_category",
        sa.Column("short_label", sa.VARCHAR(100), nullable=True),
    )
    op.add_column(
        "reimbursement_request_category",
        sa.Column("title", sa.VARCHAR(150), nullable=False),
    )

    op.add_column(
        "reimbursement_request_category",
        sa.Column("subtitle", sa.VARCHAR(150), nullable=True),
    )


def downgrade():
    op.drop_column("reimbursement_request_category", "short_label")
    op.drop_column("reimbursement_request_category", "title")
    op.drop_column(
        "reimbursement_request_category",
        "subtitle",
    )
