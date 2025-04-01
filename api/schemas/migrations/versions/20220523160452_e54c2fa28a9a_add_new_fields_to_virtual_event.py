"""Add new fields to Virtual Event

Revision ID: b9de3b30373b
Revises: 69fd5b3294f0
Create Date: 2022-05-23 16:04:52.105594+00:00

"""
from alembic import op
import sqlalchemy as sa

from models.virtual_events import Cadences


# revision identifiers, used by Alembic.
revision = "b9de3b30373b"
down_revision = "69fd5b3294f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "virtual_event",
        sa.Column("cadence", sa.Enum(Cadences), nullable=True),
    )
    op.add_column(
        "virtual_event",
        sa.Column("event_image_url", sa.String(255), nullable=True),
    )
    op.add_column(
        "virtual_event",
        sa.Column("host_specialty", sa.String(120), nullable=True),
    )
    op.add_column(
        "virtual_event",
        sa.Column("provider_profile_url", sa.String(255), nullable=True),
    )
    op.add_column(
        "virtual_event",
        sa.Column("description_body", sa.String(500), nullable=False),
    )
    op.add_column(
        "virtual_event",
        sa.Column("what_youll_learn_body", sa.String(500), nullable=False),
    )
    op.add_column(
        "virtual_event",
        sa.Column("what_to_expect_body", sa.String(500), nullable=True),
    )


def downgrade():
    op.drop_column("virtual_event", "cadence")
    op.drop_column("virtual_event", "event_image_url")
    op.drop_column("virtual_event", "host_specialty")
    op.drop_column("virtual_event", "provider_profile_url")
    op.drop_column("virtual_event", "description_body")
    op.drop_column("virtual_event", "what_youll_learn_body")
    op.drop_column("virtual_event", "what_to_expect_body")
