"""Add status index for debit cards

Revision ID: 6260fdd23e87
Revises: 679066dce759
Create Date: 2023-01-23 15:32:19.355876+00:00

"""
from alembic import op

from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard

# revision identifiers, used by Alembic.
revision = "6260fdd23e87"
down_revision = "679066dce759"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "card_status", ReimbursementWalletDebitCard.__tablename__, ["card_status"]
    )


def downgrade():
    op.drop_index("card_status", ReimbursementWalletDebitCard.__tablename__)
