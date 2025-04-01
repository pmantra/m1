"""reimbursement_credit_transaction

Revision ID: db63438f0ee5
Revises: ec6b6667de7a
Create Date: 2023-04-05 19:47:58.974510+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "db63438f0ee5"
down_revision = "f59eae1fe59e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_cycle_member_credit_transactions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
            nullable=False,
        ),
        sa.Column(
            "reimbursement_request_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request.id"),
            nullable=True,
        ),
        sa.Column(
            "reimbursement_wallet_global_procedures_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet_global_procedures.id"),
            nullable=True,
        ),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("reimbursement_cycle_member_credit_transactions")
