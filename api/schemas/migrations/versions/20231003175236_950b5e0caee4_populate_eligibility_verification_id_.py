"""populate_eligibility_verification_id_from_member_track

Revision ID: 950b5e0caee4
Revises: b48f4a5f34a3
Create Date: 2023-10-03 17:52:36.909777+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "950b5e0caee4"
down_revision = "cb361019c968"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    UPDATE maven.`backfill_reimbursement_wallet_state` brs
    INNER JOIN maven.reimbursement_wallet rw ON brs.reimbursement_wallet_id = rw.id
    INNER JOIN maven.member_track mt ON rw.organization_employee_id = mt.organization_employee_id AND rw.user_id = mt.user_id
    SET brs.eligibility_verification_id=mt.eligibility_verification_id
    WHERE rw.initial_eligibility_verification_id IS NULL
        AND mt.eligibility_verification_id IS NOT NULL
        AND brs.eligibility_member_id IS NULL and brs.eligibility_verification_id is NULL
    """
    )


def downgrade():
    op.execute(
        """
    UPDATE maven.`backfill_reimbursement_wallet_state` brs
    INNER JOIN maven.reimbursement_wallet rw ON brs.reimbursement_wallet_id = rw.id
    INNER JOIN maven.member_track mt ON rw.organization_employee_id = mt.organization_employee_id AND rw.user_id = mt.user_id
    SET brs.eligibility_verification_id=NULL
    WHERE rw.initial_eligibility_verification_id IS NULL
        AND mt.eligibility_verification_id IS NOT NULL
        AND brs.eligibility_member_id IS NULL and brs.eligibility_verification_id is NOT NULL
    """
    )
