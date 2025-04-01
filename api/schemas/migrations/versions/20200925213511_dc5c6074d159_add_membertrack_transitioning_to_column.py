"""Add 'transitioning_to' column to MemberTrack.

Revision ID: dc5c6074d159
Revises: 1a5c3216a9d7
Create Date: 2020-09-25 21:35:11.231394

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "dc5c6074d159"
down_revision = "24b2f99e93e4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_track", sa.Column("transitioning_to", sa.String(120), nullable=True)
    )


def downgrade():
    op.drop_column("member_track", "transitioning_to")
