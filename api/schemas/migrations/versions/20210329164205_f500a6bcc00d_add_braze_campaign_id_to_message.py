"""Add braze_campaign_id to message.

Revision ID: f500a6bcc00d
Revises: bedcea580bd9
Create Date: 2021-03-29 16:42:05.252843

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f500a6bcc00d"
down_revision = "bedcea580bd9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "message",
        sa.Column("braze_campaign_id", sa.String(36), default=None, nullable=True),
    )


def downgrade():
    op.drop_column("message", "braze_campaign_id")
