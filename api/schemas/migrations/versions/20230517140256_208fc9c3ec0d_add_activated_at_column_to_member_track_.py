"""add_activated_at_column_to_member_track_table

Revision ID: 208fc9c3ec0d
Revises: 157fe7553804
Create Date: 2023-05-17 14:02:56.565900+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "208fc9c3ec0d"
down_revision = "157fe7553804"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_track",
        sa.Column(
            "activated_at",
            sa.DateTime,
            server_default=sa.func.current_timestamp(),
        ),
    )


def downgrade():
    op.drop_column("member_track", "activated_at")
