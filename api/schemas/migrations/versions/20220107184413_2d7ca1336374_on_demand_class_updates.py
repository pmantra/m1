"""on-demand class updates

Revision ID: 2d7ca1336374
Revises: 779a38b5f3f5
Create Date: 2022-01-07 18:44:13.280335+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2d7ca1336374"
down_revision = "779a38b5f3f5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resource_on_demand_class",
        sa.Column(
            "resource_id", sa.Integer, sa.ForeignKey("resource.id"), primary_key=True
        ),
        sa.Column("instructor", sa.String(120), nullable=False),
        sa.Column("length", sa.Interval(), nullable=False),
    )

    # this table is similar to resource_track_phases and resource_connected_content_track_phases
    # but only allows one resource to be assigned to each track/phase
    op.create_table(
        "resource_featured_class_track_phase",
        # flask-admin requires a single primary key for editing
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "resource_id",
            sa.Integer,
            sa.ForeignKey("resource_on_demand_class.resource_id"),
            nullable=False,
        ),
        sa.Column("track_name", sa.String(120), nullable=False),
        sa.Column("phase_name", sa.String(120), nullable=False),
    )
    op.create_unique_constraint(
        "featured_class_track_phase",
        "resource_featured_class_track_phase",
        ["track_name", "phase_name"],
    )


def downgrade():
    op.drop_table("resource_featured_class_track_phase")
    op.drop_table("resource_on_demand_class")
