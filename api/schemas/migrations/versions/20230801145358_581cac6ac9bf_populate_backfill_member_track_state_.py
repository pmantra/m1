"""populate_backfill_member_track_state_table

Revision ID: 581cac6ac9bf
Revises: 4ee33fc3ab51
Create Date: 2023-08-01 14:53:58.820219+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "581cac6ac9bf"
down_revision = "110fc0b10963"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    INSERT INTO maven.`backfill_member_track_state` (member_track_id, eligibility_member_id)
    SELECT mt.id, oe.eligibility_member_id
    FROM maven.member_track mt 
    INNER JOIN maven.organization_employee oe ON mt.organization_employee_id = oe.id
    INNER JOIN maven.organization o ON oe.organization_id = o.id
    WHERE mt.eligibility_member_id IS NULL
        AND oe.eligibility_member_id IS NOT NULL 
        AND o.eligibility_type IN ('HEALTHPLAN', 'STANDARD', 'ALTERNATE', 'UNKNOWN', 'CLIENT_SPECIFIC')     
    """
    )


def downgrade():
    op.execute(
        """
    truncate table maven.`backfill_member_track_state`
    """
    )
