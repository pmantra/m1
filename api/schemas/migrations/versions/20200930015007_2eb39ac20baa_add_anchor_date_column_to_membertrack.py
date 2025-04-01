"""Add 'anchor_date' column to MemberTrack.

Revision ID: 2eb39ac20baa
Revises: dc5c6074d159
Create Date: 2020-09-30 01:50:07.830499

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2eb39ac20baa"
down_revision = "dc5c6074d159"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("member_track", sa.Column("anchor_date", sa.Date(), default=None))


def downgrade():
    op.drop_column("member_track", "anchor_date")
