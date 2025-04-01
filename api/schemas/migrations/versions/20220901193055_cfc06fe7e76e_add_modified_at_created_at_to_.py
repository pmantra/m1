"""add modified at created at to transactions

Revision ID: cfc06fe7e76e
Revises: bc6acd8e08aa
Create Date: 2022-09-01 19:30:55.315749+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cfc06fe7e76e"
down_revision = "bc6acd8e08aa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reimbursement_transaction", sa.Column("modified_at", sa.DateTime))
    op.add_column("reimbursement_transaction", sa.Column("created_at", sa.DateTime))


def downgrade():
    op.drop_column("reimbursement_transaction", "modified_at")
    op.drop_column("reimbursement_transaction", "created_at")
