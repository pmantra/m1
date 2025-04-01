"""Create virtual_event_category and virtual_event_category_track tables and add fk to virtual_event

Revision ID: 9dfe24ddc756
Revises: aaa9ff85752f
Create Date: 2022-04-21 19:01:13.014383+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9dfe24ddc756"
down_revision = "aaa9ff85752f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "virtual_event_category",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "virtual_event_category_track",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("track_name", sa.String(120), nullable=False, index=True),
        sa.Column(
            "virtual_event_category_id",
            sa.Integer,
            sa.ForeignKey("virtual_event_category.id"),
            nullable=False,
        ),
        sa.Column("availability_start_week", sa.Integer),
        sa.Column("availability_end_week", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )
    op.create_unique_constraint(
        "track_name_event_category_id",
        "virtual_event_category_track",
        ["track_name", "virtual_event_category_id"],
    )

    op.add_column("virtual_event", sa.Column("virtual_event_category_id", sa.Integer))
    op.create_foreign_key(
        "category_fk",
        "virtual_event",
        "virtual_event_category",
        ["virtual_event_category_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("category_fk", "virtual_event", type_="foreignkey")
    op.drop_column("virtual_event", "virtual_event_category_id")
    op.drop_table("virtual_event_category_track")
    op.drop_table("virtual_event_category")
