"""create_payer_list_table

Revision ID: 90b371bed622
Revises: 8f0f5b10286b
Create Date: 2023-05-23 09:39:33.971365+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "90b371bed622"
down_revision = "8f0f5b10286b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rte_payer_list",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("payer_name", sa.String(255), nullable=False),
        sa.Column("payer_code", sa.String(255), nullable=False),
    )


def downgrade():
    op.drop_table("rte_payer_list")
