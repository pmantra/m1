"""Create table practitioner_track_vgc

Revision ID: 954ad4fed0a0
Revises: 9bcb08116083
Create Date: 2022-05-25 21:59:19.733882+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "954ad4fed0a0"
down_revision = "2203e6f254f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practitioner_track_vgc",
        sa.Column(
            "practitioner_id",
            sa.Integer,
            sa.ForeignKey("practitioner_profile.user_id"),
            nullable=False,
        ),
        sa.Column("track", sa.String(120), nullable=False),
        sa.Column("vgc", sa.String(120), nullable=False),
    )
    op.create_unique_constraint(
        constraint_name="uq_prac_track_vgc",
        table_name="practitioner_track_vgc",
        columns=["practitioner_id", "track", "vgc"],
    )


def downgrade():
    op.drop_table("practitioner_track_vgc")
