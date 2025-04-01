"""Create reimbursement_wallet_users table

Revision ID: 086cf3b300fb
Revises: ebc2b742e7fa
Create Date: 2023-06-14 18:38:49.927901+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.constants import WalletUserStatus, WalletUserType


# revision identifiers, used by Alembic.
revision = "086cf3b300fb"
down_revision = "ebc2b742e7fa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_wallet_users",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("user.id"),
            unique=False,
            nullable=False,
        ),
        sa.Column("type", sa.Enum(WalletUserType), nullable=False),
        sa.Column("status", sa.Enum(WalletUserStatus), nullable=False),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("channel.id"),
            nullable=True,
        ),
        sa.Column("zendesk_ticket_id", sa.BigInteger, nullable=True),
        sa.Column("alegeus_dependent_id", sa.VARCHAR(30), nullable=True),
    )

    op.create_index(
        "idx_wallet_id_user_id",
        "reimbursement_wallet_users",
        ["reimbursement_wallet_id", "user_id"],
        unique=True,
    )


def downgrade():
    op.drop_table("reimbursement_wallet_users")
