"""provider_addenda_backfill_null_associated_answer_id

Revision ID: ab02eff69511
Revises: a10fcdbf3b4f
Create Date: 2024-02-27 14:29:13.012736+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ab02eff69511"
down_revision = "a10fcdbf3b4f"
branch_labels = None
depends_on = None


def upgrade():
    # As of right now provider addenda are no longer associated to specific answers, they are
    # associated with an entire appointment.  This may no longer be true in the future so the
    # capability is being kept, but all previously created addenda will be at the appointment level.
    op.execute("UPDATE `provider_addendum` SET `associated_answer_id` = NULL;")


def downgrade():
    pass
