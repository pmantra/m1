"""create_reimbursement_wallet_benefit_table

Revision ID: ec9249d78841
Revises: 9bffb48b5cbb
Create Date: 2023-01-30 20:11:49.358250+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ec9249d78841"
down_revision = "9bffb48b5cbb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_wallet_benefit",
        sa.Column("incremental_id", sa.Integer, primary_key=True),
        sa.Column("rand", sa.SmallInteger),
        sa.Column("checksum", sa.SmallInteger),
        sa.Column("maven_benefit_id", sa.String(16), nullable=True, unique=True),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("reimbursement_wallet_benefit")
