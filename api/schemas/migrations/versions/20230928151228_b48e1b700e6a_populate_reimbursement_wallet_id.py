"""populate_reimbursement_wallet_id

Revision ID: b48e1b700e6a
Revises: 263de358bad4
Create Date: 2023-09-28 15:12:28.182231+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b48e1b700e6a"
down_revision = "263de358bad4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    INSERT INTO maven.`backfill_reimbursement_wallet_state` (reimbursement_wallet_id) 
    SELECT id
    FROM maven.reimbursement_wallet rw
    WHERE initial_eligibility_member_id IS NULL AND initial_eligibility_verification_id IS NULL
    """
    )


def downgrade():
    # in case of downgrade, we want truncate the temp table
    op.execute(
        """
    TRUNCATE TABLE maven.`backfill_reimbursement_wallet_state`
    """
    )
