"""Add name column to MemberTrack and make ClientTrack.track simple text.

Revision ID: 06e560ec6777
Revises: 3b93df61d52b, d13386699d19
Create Date: 2020-09-10 21:25:10.320035

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from models.tracks import TrackName

revision = "06e560ec6777"
down_revision = ("3b93df61d52b", "d13386699d19")
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("member_track") as batch_op:
        batch_op.add_column(
            sa.Column("name", sa.String(120), nullable=False, index=True)
        )
        batch_op.create_index("ix_member_track_user_track_name", ["user_id", "name"])
    with op.batch_alter_table("client_track") as batch_op:
        batch_op.alter_column("track", type_=sa.String(120), existing_nullable=False)
        batch_op.create_index("ix_client_track_track", ["track"])
        batch_op.create_unique_constraint(
            "uc_client_track_organization_track", ["organization_id", "track"]
        )
    op.create_unique_constraint(
        "uc_track_extension_logic_days",
        "track_extension",
        ["extension_logic", "extension_days"],
    )


def downgrade():
    with op.batch_alter_table("member_track") as batch_op:
        batch_op.drop_index("ix_member_track_name")
        batch_op.drop_index("ix_member_track_user_track_name")
        batch_op.drop_column("name")
    with op.batch_alter_table("client_track") as batch_op:
        batch_op.drop_index("ix_client_track_track")
        batch_op.drop_constraint("uc_client_track_organization_track", type_="unique")
        batch_op.alter_column(
            "track", type_=sa.Enum(TrackName), existing_nullable=False
        )
    op.drop_constraint(
        "uc_track_extension_logic_days", "track_extension", type_="unique"
    )
