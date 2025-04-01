"""Add draft column to appointment_metadata

Revision ID: 46d399caca3d
Revises: 9d626cd02214
Create Date: 2020-11-23 18:47:18.481998

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "46d399caca3d"
down_revision = "9d626cd02214"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "appointment_metadata",
        sa.Column("draft", sa.Boolean, server_default=sa.sql.expression.false()),
    )


def downgrade():
    op.drop_column("appointment_metadata", "draft")
