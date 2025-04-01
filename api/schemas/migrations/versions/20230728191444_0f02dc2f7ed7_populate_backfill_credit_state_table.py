"""populate_backfill_credit_state_table

Revision ID: 0f02dc2f7ed7
Revises: d82e535460e5
Create Date: 2023-07-28 19:14:44.548223+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0f02dc2f7ed7"
down_revision = "d82e535460e5"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    INSERT INTO maven.`backfill_credit_state` (credit_id, eligibility_member_id)
    SELECT c.id, oe.eligibility_member_id
    FROM maven.credit c 
    INNER JOIN maven.organization_employee oe ON c.organization_employee_id = oe.id
    INNER JOIN maven.organization o ON oe.organization_id = o.id
    WHERE c.eligibility_member_id IS NULL
        AND oe.eligibility_member_id IS NOT NULL 
        AND o.eligibility_type IN ('HEALTHPLAN', 'STANDARD', 'ALTERNATE', 'UNKNOWN', 'CLIENT_SPECIFIC')     
    """
    )


def downgrade():
    op.execute(
        """
    truncate table maven.`backfill_credit_state`
    """
    )
