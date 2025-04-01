"""reimbursement_cycle_credits

Revision ID: a84d46eb3c33
Revises: ec6b6667de7a
Create Date: 2023-03-30 14:04:51.746935+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a84d46eb3c33"
down_revision = "41efe3e1bcb6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_cycle_credits",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
            nullable=False,
        ),
        sa.Column(
            "reimbursement_organization_settings_allowed_category_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_organization_settings_allowed_category.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )

    op.create_unique_constraint(
        "reimbursement_wallet_category",
        "reimbursement_cycle_credits",
        [
            "reimbursement_wallet_id",
            "reimbursement_organization_settings_allowed_category_id",
        ],
    )


def downgrade():
    op.drop_table("reimbursement_cycle_credits")
