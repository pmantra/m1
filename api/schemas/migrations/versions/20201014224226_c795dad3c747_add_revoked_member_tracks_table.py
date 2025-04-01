"""Add revoked member tracks table

Revision ID: c795dad3c747
Revises: 62f9b764cfbd
Create Date: 2020-10-14 22:42:26.576785

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c795dad3c747"
down_revision = "62f9b764cfbd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revoked_member_tracks",
        sa.Column(
            "member_track_id",
            sa.Integer,
            sa.ForeignKey("member_track.id"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("member_track_id"),
    )


def downgrade():
    op.drop_table("revoked_member_tracks")
