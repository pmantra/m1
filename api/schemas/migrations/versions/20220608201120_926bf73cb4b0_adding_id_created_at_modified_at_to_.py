"""Adding id, created_at, modified_at to practitioner_track_vgc table

Revision ID: 926bf73cb4b0
Revises: 8d26c1908f28
Create Date: 2022-06-08 20:11:20.947891+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "926bf73cb4b0"
down_revision = "32333755a20e"
branch_labels = None
depends_on = None


def upgrade():

    op.drop_table("practitioner_track_vgc")

    op.create_table(
        "practitioner_track_vgc",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
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
