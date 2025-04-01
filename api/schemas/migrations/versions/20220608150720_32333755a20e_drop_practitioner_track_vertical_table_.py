"""drop practitioner track vertical table nh

Revision ID: 32333755a20e
Revises: 8d26c1908f28
Create Date: 2022-06-08 15:07:20.915266+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "32333755a20e"
down_revision = "8d26c1908f28"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("practitioner_track_vertical")


def downgrade():
    op.create_table(
        "practitioner_track_vertical",
        sa.Column(
            "practitioner_id",
            sa.Integer,
            sa.ForeignKey("practitioner_profile.user_id"),
            nullable=False,
        ),
        sa.Column("track_name", sa.String(120), nullable=False),
        sa.Column(
            "vertical_id", sa.Integer, sa.ForeignKey("vertical.id"), nullable=False
        ),
    )

    op.create_unique_constraint(
        constraint_name="uq_prac_track_vertical",
        table_name="practitioner_track_vertical",
        columns=["practitioner_id", "vertical_id", "track_name"],
    )
