"""Add wallet dashboard tables

Revision ID: 091593868639
Revises: 1f83bf5d74d9
Create Date: 2022-08-15 17:32:41.821028+00:00

"""
import enum
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "091593868639"
down_revision = "1f83bf5d74d9"
branch_labels = None
depends_on = None


class ReimbursementWalletDashboardType(enum.Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    DISQUALIFIED = "DISQUALIFIED"


def upgrade():
    op.create_table(
        "reimbursement_wallet_dashboard",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "type",
            sa.Enum(ReimbursementWalletDashboardType),
            nullable=False,
            unique=True,
        ),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "reimbursement_wallet_dashboard_card",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("title", sa.String(255)),
        sa.Column("body", sa.Text()),
        sa.Column("img_url", sa.String(1024)),
        sa.Column("link_text", sa.String(255)),
        sa.Column("link_url", sa.String(255)),
        sa.Column("require_debit_eligible", sa.Boolean(), nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "reimbursement_wallet_dashboard_cards",
        sa.Column(
            "reimbursement_wallet_dashboard_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet_dashboard.id"),
            primary_key=True,
        ),
        sa.Column(
            "reimbursement_wallet_dashboard_card_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet_dashboard_card.id"),
            primary_key=True,
        ),
        sa.Column("order", sa.SmallInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("reimbursement_wallet_dashboard_cards")
    op.drop_table("reimbursement_wallet_dashboard_card")
    op.drop_table("reimbursement_wallet_dashboard")
