"""Add previous and bucket_id to member track

Revision ID: b3df22dd9e55
Revises: 7103d915ca26
Create Date: 2020-10-22 14:29:03.644770

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3df22dd9e55"
down_revision = "7103d915ca26"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_track",
        sa.Column(
            "previous_member_track_id",
            sa.Integer,
            sa.ForeignKey("member_track.id", name="member_track_previous_id_fk"),
            nullable=True,
        ),
    )

    op.add_column(
        "member_track",
        sa.Column("bucket_id", sa.String(36), nullable=False, index=True),
    )
    op.execute("""UPDATE member_track SET bucket_id=(SELECT uuid());""")


def downgrade():
    op.drop_constraint(
        "member_track_previous_id_fk", "member_track", type_="foreignkey"
    )
    op.drop_column("member_track", "previous_member_track_id")

    op.drop_column("member_track", "bucket_id")
