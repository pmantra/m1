"""Add unique constraint to reimbursement_request_source table

Revision ID: e7b69051607d
Revises: a3e2c9ecdc74
Create Date: 2022-12-15 23:07:51.139530+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e7b69051607d"
down_revision = "a3e2c9ecdc74"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_asset_wallet",
        "reimbursement_request_source",
        ["user_asset_id", "reimbursement_wallet_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_asset_wallet", "reimbursement_request_source", type_="unique"
    )
