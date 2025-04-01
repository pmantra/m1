"""Add webinar tables

Revision ID: 27e152002f9c
Revises: 5d30148c4225
Create Date: 2021-07-27 13:30:55.043134+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27e152002f9c"
down_revision = "5d30148c4225"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "webinar",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("uuid", sa.String(100), nullable=False),
        sa.Column("host_id", sa.String(100), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("type", sa.String(1)),
        sa.Column("duration", sa.Integer),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("join_url", sa.String(100)),
        sa.Column("agenda", sa.String(250)),
        sa.Column("start_time", sa.DateTime, nullable=False),
    )

    op.create_table(
        "user_webinars",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "webinar_id",
            sa.BigInteger,
            sa.ForeignKey("webinar.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("registrant_id", sa.String(100)),
        sa.Column("status", sa.String(50)),
    )


def downgrade():
    op.drop_table("user_webinars")
    op.drop_table("webinar")
