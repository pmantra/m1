"""Add launch_date column to client_track table

Revision ID: 51f9e5c95fef
Revises: b44162d51390
Create Date: 2020-12-09 19:55:26.612447

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "51f9e5c95fef"
down_revision = "4a7cf537683c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("client_track", sa.Column("launch_date", sa.Date(), default=None))


def downgrade():
    op.drop_column("client_track", "launch_date")
