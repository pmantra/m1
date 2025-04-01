"""add cycle credits balance FK to member credit transactions table

Revision ID: f4ece4e2ffdb
Revises: e89c83cb49d0
Create Date: 2023-05-15 15:28:31.808473+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f4ece4e2ffdb"
down_revision = "e89c83cb49d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_cycle_member_credit_transactions",
        sa.Column(
            "reimbursement_cycle_credits_id",
            sa.BigInteger,
            sa.ForeignKey(
                "reimbursement_cycle_credits.id",
                name="reimbursement_cycle_member_credit_transactions_ibfk_1",
            ),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_constraint(
        "reimbursement_cycle_member_credit_transactions_ibfk_1",
        "reimbursement_cycle_member_credit_transactions",
        type_="foreignkey",
    )
    op.drop_column(
        "reimbursement_cycle_member_credit_transactions",
        "reimbursement_cycle_credits_id",
    )
