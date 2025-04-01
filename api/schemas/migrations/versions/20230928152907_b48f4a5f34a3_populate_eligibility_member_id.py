"""populate_eligibility_member_id

Revision ID: b48f4a5f34a3
Revises: b48e1b700e6a
Create Date: 2023-09-28 15:29:07.626516+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b48f4a5f34a3"
down_revision = "92d99ff1c2f3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    UPDATE maven.`backfill_reimbursement_wallet_state` brs
    INNER JOIN maven.reimbursement_wallet rw ON brs.reimbursement_wallet_id = rw.id
    INNER JOIN maven.organization_employee oe ON rw.organization_employee_id = oe.id
    INNER JOIN maven.organization o ON oe.organization_id = o.id
    SET brs.eligibility_member_id=oe.eligibility_member_id
    WHERE rw.initial_eligibility_member_id IS NULL
        AND oe.eligibility_member_id IS NOT NULL 
        AND o.eligibility_type IN ('HEALTHPLAN', 'STANDARD', 'ALTERNATE', 'UNKNOWN', 'CLIENT_SPECIFIC')
        AND brs.eligibility_member_id IS NULL
    """
    )


def downgrade():
    op.execute(
        """
    UPDATE maven.`backfill_reimbursement_wallet_state` brs
    INNER JOIN maven.reimbursement_wallet rw ON brs.reimbursement_wallet_id = rw.id
    INNER JOIN maven.organization_employee oe ON rw.organization_employee_id = oe.id
    INNER JOIN maven.organization o ON oe.organization_id = o.id
    SET brs.eligibility_member_id=NULL
    WHERE rw.initial_eligibility_member_id IS NULL
        AND oe.eligibility_member_id IS NOT NULL 
        AND o.eligibility_type IN ('HEALTHPLAN', 'STANDARD', 'ALTERNATE', 'UNKNOWN', 'CLIENT_SPECIFIC')
        AND brs.eligibility_member_id IS NOT NULL
    """
    )
