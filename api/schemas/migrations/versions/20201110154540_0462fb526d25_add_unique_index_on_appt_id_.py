"""Add unique index on appt id/questionnaire id to recorded answer sets

Revision ID: 0462fb526d25
Revises: 0e7f9eec9a31
Create Date: 2020-11-10 15:45:40.490431

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0462fb526d25"
down_revision = "0e7f9eec9a31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "appt_id_questionnaire_id",
        "recorded_answer_set",
        ["appointment_id", "questionnaire_id"],
    )


def downgrade():
    op.drop_constraint(
        "appt_id_questionnaire_id", "recorded_answer_set", type_="unique"
    )
