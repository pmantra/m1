"""add not null constraint to reimbursement source wallet id

Revision ID: d78f0bf020b5
Revises: a73f614cce8f
Create Date: 2020-05-18 21:51:40.007261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d78f0bf020b5"
down_revision = "a73f614cce8f"
branch_labels = None
depends_on = None


def upgrade():
    # We must drop and re-add the foreign key constraint while altering the column
    op.drop_constraint(
        "reimbursement_request_source_wallet_id_fk",
        "reimbursement_request_source",
        type_="foreignkey",
    )
    op.alter_column(
        "reimbursement_request_source",
        "reimbursement_wallet_id",
        nullable=False,
        existing_type=sa.BigInteger,
    )
    op.create_foreign_key(
        "reimbursement_request_source_wallet_id_fk",
        "reimbursement_request_source",
        "reimbursement_wallet",
        ["reimbursement_wallet_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "reimbursement_request_source_wallet_id_fk",
        "reimbursement_request_source",
        type_="foreignkey",
    )
    op.alter_column(
        "reimbursement_request_source",
        "reimbursement_wallet_id",
        nullable=True,
        existing_type=sa.BigInteger,
    )
    op.create_foreign_key(
        "reimbursement_request_source_wallet_id_fk",
        "reimbursement_request_source",
        "reimbursement_wallet",
        ["reimbursement_wallet_id"],
        ["id"],
    )
