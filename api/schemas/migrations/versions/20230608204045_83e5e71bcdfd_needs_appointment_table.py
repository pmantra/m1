"""needs-appointment-table

Revision ID: 83e5e71bcdfd
Revises: c469e0357e1b
Create Date: 2023-06-08 20:40:45.283420+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "83e5e71bcdfd"
down_revision = "c469e0357e1b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "need_appointment",
        sa.Column(
            "appointment_id",
            sa.Integer,
            sa.ForeignKey("appointment.id"),
            primary_key=True,
        ),
        sa.Column(
            "need_id",
            sa.Integer,
            sa.ForeignKey("need.id"),
            primary_key=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("need_appointment")
