"""needs-appointment-unique-restriction

Revision ID: ff8fd19f6287
Revises: 47c01442925e
Create Date: 2023-06-16 14:30:24.042144+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ff8fd19f6287"
down_revision = "47c01442925e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_appointment_id", "need_appointment", ["appointment_id"]
    )


def downgrade():
    op.drop_constraint("uq_appointment_id", "need_appointment", "unique")
