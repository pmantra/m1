"""Add appointment id to recorded answer set

Revision ID: 3d9cd001e15c
Revises: 56b14b37ba34
Create Date: 2020-10-22 20:57:58.295201

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3d9cd001e15c"
down_revision = "56b14b37ba34"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recorded_answer_set",
        sa.Column(
            "appointment_id",
            sa.Integer,
            sa.ForeignKey("appointment.id", name="fk_rec_answer_set_appt_id"),
        ),
    )


def downgrade():
    op.drop_constraint(
        "fk_rec_answer_set_appt_id", "recorded_answer_set", type_="foreignkey"
    )
    op.drop_column("recorded_answer_set", "appointment_id")
