"""Add created_at to assessment tracks

Revision ID: e20f8aa43430
Revises: 36603f7ee60a
Create Date: 2022-03-29 18:16:34.412160+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e20f8aa43430"
down_revision = "36603f7ee60a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assessment_track_relationships", sa.Column("created_at", sa.DateTime)
    )


def downgrade():
    op.drop_column("assessment_track_relationships", "created_at")
