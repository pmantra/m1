"""add channel_id and status composite index

Revision ID: 122b8d0d139c
Revises: 5cb837be51af
Create Date: 2025-01-27 23:55:32.850298+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "122b8d0d139c"
down_revision = "5cb837be51af"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE INDEX idx_status_channel_id ON message (status, channel_id)")


def downgrade():
    op.execute("DROP INDEX idx_status_channel_id on message")
