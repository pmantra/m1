"""need-needcategories-string-track-tables

Revision ID: 03a20c617bee
Revises: e8076a26d78b
Create Date: 2023-04-19 23:48:45.753371+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "03a20c617bee"
down_revision = "e8076a26d78b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tracks_need_category",
        sa.Column("track_name", sa.String(120), primary_key=True),
        sa.Column(
            "need_category_id",
            sa.Integer,
            sa.ForeignKey("need_category.id"),
            primary_key=True,
        ),
    )
    op.create_table(
        "tracks_need",
        sa.Column("track_name", sa.String(120), primary_key=True),
        sa.Column(
            "need_id",
            sa.Integer,
            sa.ForeignKey("need.id"),
            primary_key=True,
        ),
    )
    op.drop_table("member_track_need_category")


def downgrade():
    op.drop_table("tracks_need_category")
    op.drop_table("tracks_need")
    op.create_table(
        "member_track_need_category",
        sa.Column(
            "track_id",
            sa.Integer,
            sa.ForeignKey("member_track.id"),
            primary_key=True,
        ),
        sa.Column(
            "need_category_id",
            sa.Integer,
            sa.ForeignKey("need_category.id"),
            primary_key=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime),
    )
