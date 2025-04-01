"""Add dispatch_id to messages

Revision ID: 73b0775db725
Revises: f7ca34b5d45c
Create Date: 2021-08-19 17:57:01.657224+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bf5408980bf9"
down_revision = "9afd71a96afb"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "message",
        sa.Column("braze_dispatch_id", sa.String(36), default=None, nullable=True),
    )


def downgrade():
    op.drop_column("message", "braze_dispatch_id")
