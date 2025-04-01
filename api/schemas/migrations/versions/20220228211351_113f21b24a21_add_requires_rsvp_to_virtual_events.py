"""Add Rsvp Required to Virtual Event

Revision ID: 113f21b24a21
Revises: 4bafe3966f5f
Create Date: 2022-02-28 21:13:51.891587+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "113f21b24a21"
down_revision = "4bafe3966f5f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "virtual_event",
        sa.Column("rsvp_required", sa.Boolean, nullable=False, default=True),
    )


def downgrade():
    op.drop_column("virtual_event", "rsvp_required")
