"""add_deleted_date_to_verticals

Revision ID: 5b920d2d16b0
Revises: e53054c5de7a
Create Date: 2022-10-19 19:18:38.241461+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b920d2d16b0"
down_revision = "e53054c5de7a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vertical", sa.Column("deleted_at", sa.DateTime(), default=None))


def downgrade():
    op.drop_column("vertical", "deleted_at")
