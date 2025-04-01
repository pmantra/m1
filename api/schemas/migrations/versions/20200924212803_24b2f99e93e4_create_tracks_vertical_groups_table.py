"""Create tracks_vertical_groups table

Revision ID: 24b2f99e93e4
Revises: 1a5c3216a9d7
Create Date: 2020-09-24 21:28:03.144843

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "24b2f99e93e4"
down_revision = "1a5c3216a9d7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tracks_vertical_groups",
        sa.Column("track_name", sa.String(120), primary_key=True),
        sa.Column(
            "vertical_group_id",
            sa.Integer,
            sa.ForeignKey("vertical_group.id"),
            primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("tracks_vertical_groups")
