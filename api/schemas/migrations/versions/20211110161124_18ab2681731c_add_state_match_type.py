"""Test

Revision ID: 18ab2681731c
Revises: 189578402bdb
Create Date: 2021-11-10 16:11:24.485888+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "18ab2681731c"
down_revision = "189578402bdb"
branch_labels = None
depends_on = None


def upgrade():
    from provider_matching.models.constants import StateMatchType

    op.add_column(
        "appointment",
        sa.Column(
            "state_match_type",
            sa.Enum(
                StateMatchType, values_callable=lambda _enum: [e.value for e in _enum]
            ),
        ),
    )


def downgrade():
    op.drop_column("appointment", "state_match_type")
