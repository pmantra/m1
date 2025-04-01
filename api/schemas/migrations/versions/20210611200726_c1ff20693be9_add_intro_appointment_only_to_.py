"""Add intro_appointment_only to questionnaire table

Revision ID: c1ff20693be9
Revises: 53fae051ade4
Create Date: 2021-06-11 20:07:26.081956+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1ff20693be9"
down_revision = "53fae051ade4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "questionnaire", sa.Column("intro_appointment_only", sa.Boolean, nullable=True)
    )
    op.add_column(
        "questionnaire", sa.Column("track_name", sa.String(120), nullable=True)
    )


def downgrade():
    op.drop_column("questionnaire", "intro_appointment_only")
    op.drop_column("questionnaire", "track_name")
