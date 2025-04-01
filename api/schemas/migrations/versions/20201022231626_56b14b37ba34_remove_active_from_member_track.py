"""Remove active from member track

Revision ID: 56b14b37ba34
Revises: b3df22dd9e55
Create Date: 2020-10-22 23:16:26.435314

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "56b14b37ba34"
down_revision = "b3df22dd9e55"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("member_track", "active")


def downgrade():
    op.add_column("member_track", sa.Column("active", sa.Boolean, nullable=False))
    op.execute("""UPDATE member_track SET active = 1 WHERE ended_at IS NULL;""")
