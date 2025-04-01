"""Content saving

Revision ID: e33216ee8b6e
Revises: 88b5b59b4150
Create Date: 2023-03-21 17:37:50.673224+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e33216ee8b6e"
down_revision = "88b5b59b4150"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "member_resources",
        sa.Column(
            "member_id",
            sa.Integer,
            sa.ForeignKey("member_profile.user_id", ondelete="cascade"),
            primary_key=True,
        ),
        sa.Column(
            "resource_id",
            sa.Integer,
            sa.ForeignKey("resource.id", ondelete="cascade"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("member_resources")
