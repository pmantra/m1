"""backfill_rw_id_to_oed

Revision ID: c383c0f3c9ae
Revises: 6219ce1fefcf
Create Date: 2023-11-07 18:42:41.365719+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c383c0f3c9ae"
down_revision = "4aca2513b6d1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE maven.organization_employee_dependent oed
        INNER JOIN (
            SELECT organization_employee_id, MAX(id) AS max_id FROM maven.reimbursement_wallet rw 
            WHERE `state` = 'QUALIFIED'  GROUP BY organization_employee_id
        ) max_qualified_rw
        ON max_qualified_rw.organization_employee_id = oed.organization_employee_id
        SET oed.reimbursement_wallet_id = max_qualified_rw.max_id
        WHERE oed.reimbursement_wallet_id IS NULL
    """
    )


def downgrade():
    op.execute(
        """
        UPDATE maven.organization_employee_dependent oed
        INNER JOIN (
            SELECT organization_employee_id, MAX(id) AS max_id FROM maven.reimbursement_wallet rw 
            WHERE `state` = 'QUALIFIED'  GROUP BY organization_employee_id
        ) max_qualified_rw
        ON max_qualified_rw.organization_employee_id = oed.organization_employee_id
        SET oed.reimbursement_wallet_id = NULL
        WHERE oed.reimbursement_wallet_id = max_qualified_rw.max_id
    """
    )
