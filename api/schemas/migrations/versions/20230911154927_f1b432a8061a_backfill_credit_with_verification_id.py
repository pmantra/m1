"""backfill_credit_with_verification_id

Revision ID: f1b432a8061a
Revises: 033a218da593
Create Date: 2023-09-11 15:49:27.361049+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f1b432a8061a"
down_revision = "033a218da593"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    UPDATE maven.credit c JOIN maven.backfill_verification_state bvs
    ON c.user_id = bvs.user_id AND c.organization_employee_id = bvs.organization_employee_id
    SET c.eligibility_verification_id = bvs.backfill_verification_id
    WHERE c.eligibility_verification_id IS NULL 
    AND c.eligibility_member_id IS NULL 
    AND c.organization_employee_id IS NOT NULL
    """
    )


def downgrade():
    # update the eligibility_verification_id back.
    # eligibility_verification_id is not in use, should be all null before back fill
    op.execute(
        """
    UPDATE maven.credit c JOIN maven.backfill_verification_state bvs
    ON c.user_id = bvs.user_id AND c.organization_employee_id = bvs.organization_employee_id
    SET c.eligibility_verification_id = NULL
    WHERE c.eligibility_verification_id IS NOT NULL 
    AND c.eligibility_member_id is NULL 
    AND c.organization_employee_id IS NOT NULL
    """
    )
