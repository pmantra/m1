"""Add unique index for card_proxy_number

Revision ID: 7cdb82dc8091
Revises: 4e455b0d50dd
Create Date: 2022-10-14 18:41:02.957011+00:00

"""
from alembic import op
import sqlalchemy as sa
from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard


# revision identifiers, used by Alembic.

revision = "7cdb82dc8091"
down_revision = "4e455b0d50dd"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        ReimbursementWalletDebitCard.__tablename__,
        "card_proxy_number",
        type_=sa.String(32),
        existing_type=sa.String(255),
        existing_nullable=False,
    )
    op.create_index(
        "card_proxy_number",
        ReimbursementWalletDebitCard.__tablename__,
        ["card_proxy_number"],
        unique=True,
    )


def downgrade():
    op.drop_index("card_proxy_number", ReimbursementWalletDebitCard.__tablename__)
    op.alter_column(
        ReimbursementWalletDebitCard.__tablename__,
        "card_proxy_number",
        type_=sa.String(255),
        existing_type=sa.String(32),
        existing_nullable=False,
    )
