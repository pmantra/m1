"""add_start_date_to_member_track_table

Revision ID: f59eae1fe59e
Revises: a84d46eb3c33
Create Date: 2023-04-10 17:23:06.990377+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f59eae1fe59e"
down_revision = "a84d46eb3c33"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_track",
        sa.Column("start_date", sa.Date, nullable=True),
    )


def downgrade():
    op.drop_column("member_track", "start_date")
