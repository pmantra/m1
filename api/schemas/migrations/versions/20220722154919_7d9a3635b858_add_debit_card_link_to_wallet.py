"""Add debit card link to wallet

Revision ID: 7d9a3635b858
Revises: bcd4ff8b7371
Create Date: 2022-07-22 15:49:19.080271+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers,tt used by Alembic.
from wallet.models.reimbursement_wallet import ReimbursementWallet

revision = "7d9a3635b858"
down_revision = "bcd4ff8b7371"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        ReimbursementWallet.__tablename__,
        sa.Column("reimbursement_wallet_debit_card_id", sa.BigInteger, nullable=True),
    )


def downgrade():
    op.drop_column(
        ReimbursementWallet.__tablename__, "reimbursement_wallet_debit_card_id"
    )
