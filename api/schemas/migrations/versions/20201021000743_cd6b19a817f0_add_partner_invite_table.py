"""Add partner invite table

Revision ID: cd6b19a817f0
Revises: 0e7f9eec9a31
Create Date: 2020-10-21 00:07:43.366312

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cd6b19a817f0"
down_revision = "46d399caca3d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "partner_invite",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "created_by_user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False
        ),
        sa.Column("json", sa.Text, nullable=True),
        sa.Column("claimed", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )

    op.create_index("ik_created_by_user_id", "partner_invite", ["created_by_user_id"])


def downgrade():
    op.drop_table("partner_invite")
