"""remap credit transaction FK from wallet to balance

Revision ID: e89c83cb49d0
Revises: be652872e1c3
Create Date: 2023-05-10 15:50:42.336110+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e89c83cb49d0"
down_revision = "be652872e1c3"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "reimbursement_cycle_member_credit_transactions_ibfk_1",
        "reimbursement_cycle_member_credit_transactions",
        type_="foreignkey",
    )
    op.drop_column(
        "reimbursement_cycle_member_credit_transactions", "reimbursement_wallet_id"
    )


def downgrade():
    op.add_column(
        "reimbursement_cycle_member_credit_transactions",
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey(
                "reimbursement_wallet.id",
                name="reimbursement_cycle_member_credit_transactions_ibfk_1",
            ),
            nullable=True,
        ),
    )
