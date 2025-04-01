"""add is_prepaid column to reimbursement_transaction table

Revision ID: ba9c788ac7c1
Revises: ec4381c09d26
Create Date: 2022-10-13 14:32:38.541470+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ba9c788ac7c1"
down_revision = "ec4381c09d26"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_transaction",
        sa.Column("is_prepaid", sa.Boolean, nullable=False, default=False),
    )


def downgrade():
    op.drop_column("reimbursement_transaction", "is_prepaid")
