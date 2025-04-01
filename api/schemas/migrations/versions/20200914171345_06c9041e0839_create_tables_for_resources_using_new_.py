"""Create tables for resources using new Tracks models

Revision ID: 06c9041e0839
Revises: fd485f326679
Create Date: 2020-09-14 17:13:45.699791

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "06c9041e0839"
down_revision = "fd485f326679"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resource_tracks",
        sa.Column(
            "resource_id", sa.Integer, sa.ForeignKey("resource.id"), primary_key=True
        ),
        sa.Column("track_name", sa.String(120), primary_key=True),
    )
    op.create_table(
        "resource_track_phases",
        sa.Column(
            "resource_id", sa.Integer, sa.ForeignKey("resource.id"), primary_key=True
        ),
        sa.Column("track_name", sa.String(120), primary_key=True),
        sa.Column("phase_name", sa.String(120), primary_key=True),
    )
    op.create_table(
        "resource_connected_content_track_phases",
        sa.Column(
            "resource_id", sa.Integer, sa.ForeignKey("resource.id"), primary_key=True
        ),
        sa.Column("track_name", sa.String(120), primary_key=True),
        sa.Column("phase_name", sa.String(120), primary_key=True),
    )


def downgrade():
    op.drop_table("resource_tracks")
    op.drop_table("resource_track_phases")
    op.drop_table("resource_connected_content_track_phases")
