"""create-global-procedures-table

Revision ID: 3b93b7ef5abe
Revises: 81cdab83bb0a
Create Date: 2023-03-27 17:08:23.006956+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3b93b7ef5abe"
down_revision = "81cdab83bb0a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_wallet_global_procedures",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String(191), nullable=False, unique=True),
        sa.Column("credits", sa.SmallInteger, nullable=False),
        sa.Column("annual_limit", sa.SmallInteger, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
        sa.Column("deleted_at", sa.DateTime, default=None, nullable=True),
    )


def downgrade():
    op.drop_table("reimbursement_wallet_global_procedures")
