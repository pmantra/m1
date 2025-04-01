"""backfill_analytics_cols_for_reimbursement_wallet

Revision ID: 166cbf571101
Revises: 950b5e0caee4
Create Date: 2023-10-05 20:06:41.988946+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "166cbf571101"
down_revision = "dbf6e0a5f062"
branch_labels = None
depends_on = None


def upgrade():
    # backfill initial_eligibility_member_id
    op.execute(
        """
        UPDATE maven.reimbursement_wallet rw 
        INNER JOIN maven.backfill_reimbursement_wallet_state brws ON rw.id = reimbursement_wallet_id
        SET rw.initial_eligibility_member_id = brws.eligibility_member_id
        WHERE brws.eligibility_member_id IS NOT NULL 
        AND rw.initial_eligibility_member_id IS NULL
    """
    )

    # backfill initial_eligibility_verification_id
    op.execute(
        """
        UPDATE maven.reimbursement_wallet rw 
        INNER JOIN maven.backfill_reimbursement_wallet_state brws ON rw.id = reimbursement_wallet_id
        SET rw.initial_eligibility_verification_id = brws.eligibility_verification_id
        WHERE brws.eligibility_verification_id IS NOT NULL 
        AND rw.initial_eligibility_verification_id IS NULL
    """
    )


def downgrade():
    op.execute(
        """
        UPDATE maven.reimbursement_wallet rw 
        INNER JOIN maven.backfill_reimbursement_wallet_state brws ON rw.id = reimbursement_wallet_id
        SET rw.initial_eligibility_member_id = NULL
        WHERE brws.eligibility_member_id IS NOT NULL 
        AND rw.initial_eligibility_member_id IS NOT NULL
    """
    )

    op.execute(
        """
        UPDATE maven.reimbursement_wallet rw 
        INNER JOIN maven.backfill_reimbursement_wallet_state brws ON rw.id = reimbursement_wallet_id
        SET rw.initial_eligibility_verification_id = NULL
        WHERE brws.eligibility_verification_id IS NOT NULL 
        AND rw.initial_eligibility_verification_id IS NOT NULL
    """
    )
