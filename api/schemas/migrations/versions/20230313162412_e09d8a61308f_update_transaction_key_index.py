"""Update transaction key index

Revision ID: e09d8a61308f
Revises: df4d1f49b51a
Create Date: 2023-03-13 16:24:12.375730+00:00

"""
from alembic import op

from wallet.models.reimbursement import ReimbursementTransaction

# revision identifiers, used by Alembic.
revision = "e09d8a61308f"
down_revision = "df4d1f49b51a"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "alegeus_transaction_key",
        ReimbursementTransaction.__tablename__,
        type_="unique",
    )
    op.create_unique_constraint(
        "transaction_key_sequence_number",
        ReimbursementTransaction.__tablename__,
        ["alegeus_transaction_key", "sequence_number"],
    )


def downgrade():
    op.drop_constraint(
        "transaction_key_sequence_number",
        ReimbursementTransaction.__tablename__,
        type_="unique",
    )
    op.create_unique_constraint(
        "alegeus_transaction_key",
        ReimbursementTransaction.__tablename__,
        ["alegeus_transaction_key"],
    )
