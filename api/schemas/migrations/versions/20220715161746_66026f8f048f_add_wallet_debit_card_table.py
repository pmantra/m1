"""Add Wallet debit card table

Revision ID: 66026f8f048f
Revises: 4318fa20a399
Create Date: 2022-07-15 16:17:46.894927+00:00

"""

from alembic import op
import sqlalchemy as sa

from utils.data import TinyIntEnum
from wallet.models.constants import CardStatus, CardStatusReason

# revision identifiers, used by Alembic.
revision = "66026f8f048f"
down_revision = "d9e810b26abb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_wallet_debit_card",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
            nullable=False,
        ),
        sa.Column("card_proxy_number", sa.String(255), nullable=False),
        sa.Column("card_last_4_digits", sa.CHAR(4), nullable=False),
        sa.Column(
            "card_status", sa.Enum(CardStatus), nullable=False, default=CardStatus.NEW
        ),
        sa.Column(
            "card_status_reason",
            TinyIntEnum(CardStatusReason, unsigned=True),
            nullable=False,
            default=CardStatusReason.NONE,
        ),
        sa.Column("first_name", sa.String(255), nullable=False),
        sa.Column("last_name", sa.String(255), nullable=False),
        sa.Column("phone_number", sa.String(255), nullable=False),
        sa.Column("created_date", sa.Date, default=None),
        sa.Column("issued_date", sa.Date, default=None),
        sa.Column("shipped_date", sa.Date, default=None),
        sa.Column("shipping_tracking_number", sa.String(255), default=None),
    )


def downgrade():
    op.drop_table("reimbursement_wallet_debit_card")
