"""Add track_extension_id to member track

Revision ID: 7946c3528587
Revises: 3d9cd001e15c
Create Date: 2020-10-28 13:19:18.244823

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7946c3528587"
down_revision = "3d9cd001e15c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_track",
        sa.Column(
            "track_extension_id",
            sa.Integer,
            sa.ForeignKey("track_extension.id", name="member_track_extension_id_fk"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_constraint(
        "member_track_extension_id_fk", "member_track", type_="foreignkey"
    )
    op.drop_column("member_track", "track_extension_id")
