"""sc-98190 member availability request

Revision ID: baf07832e4c9
Revises: b9de3b30373b
Create Date: 2022-07-07 18:58:26.251846+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "baf07832e4c9"
down_revision = "b9de3b30373b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "availability_notification_request",
        sa.Column("member_timezone_offset", sa.Integer, nullable=True, default=None),
    )

    op.create_table(
        "availability_request_member_times",
        sa.Column(
            "availability_notification_request_id",
            sa.Integer,
            sa.ForeignKey("availability_notification_request.id"),
            nullable=False,
        ),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
    )


def downgrade():
    op.drop_column("availability_notification_request", "member_timezone_offset")
    op.drop_table("availability_request_member_times")
