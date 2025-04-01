"""Add ended_at on MemberTrack

Revision ID: 843f53b7a0c9
Revises: 7041db613d61, a5af85c492c4
Create Date: 2020-08-20 18:16:34.683095

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "843f53b7a0c9"
down_revision = ("7041db613d61", "a5af85c492c4")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("member_track", sa.Column("ended_at", sa.DateTime, nullable=True))


def downgrade():
    op.drop_column("member_track", "ended_at")
