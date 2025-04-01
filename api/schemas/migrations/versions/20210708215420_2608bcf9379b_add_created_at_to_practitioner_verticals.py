"""Add created_at to practitioner_verticals

Revision ID: 2608bcf9379b
Revises: bf345a0650e9
Create Date: 2021-07-08 21:54:20.120167+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2608bcf9379b"
down_revision = "bf345a0650e9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("practitioner_verticals", sa.Column("created_at", sa.DateTime))


def downgrade():
    op.drop_column("practitioner_verticals", "created_at")
