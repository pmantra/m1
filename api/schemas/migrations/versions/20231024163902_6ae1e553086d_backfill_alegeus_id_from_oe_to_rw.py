"""backfill_alegeus_id_from_oe_to_rw

Revision ID: 6ae1e553086d
Revises: 96c4b2926832
Create Date: 2023-10-24 16:39:02.593353+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6ae1e553086d"
down_revision = "999c013aa77f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    UPDATE maven.reimbursement_wallet rw
    INNER JOIN maven.organization_employee oe ON rw.organization_employee_id  = oe.id 
    SET rw.alegeus_id = oe.alegeus_id
    WHERE oe.alegeus_id IS NOT NULL AND rw.alegeus_id IS NULL
    """
    )


def downgrade():
    op.execute(
        """
    UPDATE maven.reimbursement_wallet rw
    INNER JOIN maven.organization_employee oe ON rw.organization_employee_id  = oe.id 
    SET rw.alegeus_id = NULL
    WHERE oe.alegeus_id IS NOT NULL AND rw.alegeus_id IS NOT NULL
    """
    )
