"""Add trip id to bms order

Revision ID: 6b73786c6e68
Revises: cbee1290701b
Create Date: 2021-10-22 20:28:28.152868+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6b73786c6e68"
down_revision = "cbee1290701b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bms_order",
        sa.Column("external_trip_id", sa.String(128), nullable=True),
    )


def downgrade():
    op.drop_column("bms_order", "external_trip_id")
