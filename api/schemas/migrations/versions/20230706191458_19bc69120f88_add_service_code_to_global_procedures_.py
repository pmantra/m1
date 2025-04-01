"""add_service_code_to_global_procedures_table

Revision ID: 19bc69120f88
Revises: a18b855f4c40
Create Date: 2023-07-06 19:14:58.577903+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "19bc69120f88"
down_revision = "a18b855f4c40"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_wallet_global_procedures",
        sa.Column("service_code", sa.String(255), nullable=False),
    )


def downgrade():
    op.drop_column("reimbursement_wallet_global_procedures", "service_code")
