"""add_optional_to_agreement

Revision ID: 72211219bc7a
Revises: c0cadddbdb44
Create Date: 2023-02-01 16:20:59.911813+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "72211219bc7a"
down_revision = "c0cadddbdb44"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agreement",
        sa.Column("optional", sa.Boolean, nullable=True, default=False),
    )


def downgrade():
    op.drop_column("agreement", "optional")
