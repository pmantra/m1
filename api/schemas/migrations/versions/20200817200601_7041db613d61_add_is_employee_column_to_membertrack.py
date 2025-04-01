"""Add is_employee column to MemberTrack

Revision ID: 7041db613d61
Revises: 5ee926ea8919
Create Date: 2020-08-17 20:06:01.399775

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7041db613d61"
down_revision = "5ee926ea8919"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("member_track", sa.Column("is_employee", sa.Boolean, default=True))


def downgrade():
    op.drop_column("member_track", "is_employee")
