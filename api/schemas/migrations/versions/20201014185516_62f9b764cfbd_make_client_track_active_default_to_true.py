"""Make client track active default to true

Revision ID: 62f9b764cfbd
Revises: 4f1928e7fe3f
Create Date: 2020-10-14 18:55:16.707310

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "62f9b764cfbd"
down_revision = "4f1928e7fe3f"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "client_track",
        "active",
        server_default=expression.true(),
        existing_type=sa.Boolean,
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "client_track",
        "active",
        server_default=None,
        existing_type=sa.Boolean,
        existing_nullable=False,
    )
