"""Add note to practitioner profile table

Revision ID: e5de7affd119
Revises: 18ab2681731c
Create Date: 2021-11-11 17:48:54.323081+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5de7affd119"
down_revision = "18ab2681731c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("practitioner_profile", sa.Column("note", sa.Text()))


def downgrade():
    op.drop_column("practitioner_profile", "note")
