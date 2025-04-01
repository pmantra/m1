"""add_created_at_index_to_message

Revision ID: 8aa0fa31c6e5
Revises: 873b5f882e66
Create Date: 2024-10-07 17:04:42.379003+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "8aa0fa31c6e5"
down_revision = "e1f6523d9396"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE INDEX idx_message_created_at ON message(created_at);")


def downgrade():
    op.execute("DROP INDEX idx_message_created_at ON message;")
