"""remove-availability-table

Revision ID: 532874a11410
Revises: 1fde6e015df6
Create Date: 2023-02-21 16:10:03.011835+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DOUBLE


# revision identifiers, used by Alembic.
revision = "532874a11410"
down_revision = "1fde6e015df6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "availability" in tables:
        op.drop_table("availability")


def downgrade():
    class AvailabilityStatus(str, enum.Enum):
        BOOKED = "BOOKED"
        FREE = "FREE"
        DELETED = "DELETED"

    op.create_table(
        "availability",
        sa.Column("id", sa.Integer, nullable=False, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "product_id", sa.Integer, sa.ForeignKey("product.id"), nullable=False
        ),
        sa.Column("product_price", DOUBLE(precision=8, scale=2), nullable=False),
        sa.Column(
            "vertical_id", sa.Integer, sa.ForeignKey("vertical.id"), nullable=False
        ),
        sa.Column("can_prescribe", sa.Boolean, nullable=False),
        sa.Column(
            "schedule_event_id",
            sa.Integer,
            sa.ForeignKey("schedule_event.id"),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime, nullable=False),
        sa.Column("duration", sa.Integer, nullable=False),
        sa.Column(
            "status",
            sa.Enum(AvailabilityStatus),
            server_default=AvailabilityStatus.FREE,
        ),
        sa.Column("appointment_id", sa.Integer, sa.ForeignKey("appointment.id")),
        sa.Column("credit_id", sa.Integer, sa.ForeignKey("credit.id")),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime),
    )
