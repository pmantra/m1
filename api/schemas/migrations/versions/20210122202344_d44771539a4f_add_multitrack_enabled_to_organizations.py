"""Add multitrack_enabled to organizations

Revision ID: d44771539a4f
Revises: 937c1024f7d2
Create Date: 2021-01-22 20:23:44.383491

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d44771539a4f"
down_revision = "937c1024f7d2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization",
        sa.Column("multitrack_enabled", sa.Boolean, default=False, nullable=False),
    )


def downgrade():
    op.drop_column("organization", "multitrack_enabled")
