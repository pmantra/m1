"""add cancelled columns to BMSOrders

Revision ID: 937c1024f7d2
Revises: c861d8a4b5d5
Create Date: 2021-01-12 19:07:14.662322

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "937c1024f7d2"
down_revision = "c861d8a4b5d5"
branch_labels = None
depends_on = None


class CancellationReasons(enum.Enum):
    NOT_CANCELLED = "not_cancelled"
    NON_WORK_TRAVEL = "non_work_travel"
    WORK_TRIP_CANCELLED = "work_trip_cancelled"
    WORK_TRIP_RESCHEDULED = "work_trip_rescheduled"
    OTHER = "other"


def upgrade():
    op.add_column(
        "bms_order",
        sa.Column("is_cancelled", sa.Boolean, nullable=False, default=False),
    )
    op.add_column(
        "bms_order",
        sa.Column(
            "cancellation_reason",
            sa.Enum(CancellationReasons),
            default=CancellationReasons.NOT_CANCELLED,
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("bms_order", "is_cancelled")
    op.drop_column("bms_order", "cancellation_reason")
