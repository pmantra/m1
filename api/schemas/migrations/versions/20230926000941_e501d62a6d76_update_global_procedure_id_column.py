"""update global_procedure id column

Revision ID: e501d62a6d76
Revises: a5fc02547067
Create Date: 2023-09-26 00:09:41.159431+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e501d62a6d76"
down_revision = "a5fc02547067"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_cycle_member_credit_transactions",
        sa.Column(
            "global_procedure_id",
            sa.String(36),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "reimbursement_cycle_member_credit_transactions", "global_procedure_id"
    )
