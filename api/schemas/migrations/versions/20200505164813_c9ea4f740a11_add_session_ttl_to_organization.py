"""add session_ttl to Organization

Revision ID: c9ea4f740a11
Revises: 6283041ec8b7
Create Date: 2020-05-05 16:48:13.617444

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9ea4f740a11"
down_revision = "6283041ec8b7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("organization", sa.Column("session_ttl", sa.Integer))


def downgrade():
    op.drop_column("organization", "session_ttl")
