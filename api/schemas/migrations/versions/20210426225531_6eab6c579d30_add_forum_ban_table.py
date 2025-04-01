"""Add forum_ban table

Revision ID: 6eab6c579d30
Revises: bf3d24ff2cdc
Create Date: 2021-04-26 22:55:31.850489+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6eab6c579d30"
down_revision = "bf3d24ff2cdc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forum_ban",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "created_by_user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("forum_ban")
