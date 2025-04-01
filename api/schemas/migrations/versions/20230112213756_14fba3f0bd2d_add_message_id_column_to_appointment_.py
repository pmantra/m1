"""add_message_id_column_to_appointment_metadata_table

Revision ID: 14fba3f0bd2d
Revises: 931b280390ef
Create Date: 2023-01-12 21:37:56.918411+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "14fba3f0bd2d"
down_revision = "23e09b6ddd78"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "appointment_metadata",
        sa.Column("message_id", sa.Integer, sa.ForeignKey("message.id"), nullable=True),
    )


def downgrade():
    op.drop_constraint(
        "appointment_metadata_ibfk_2", "appointment_metadata", type_="foreignkey"
    )
    op.drop_column("appointment_metadata", "message_id")
