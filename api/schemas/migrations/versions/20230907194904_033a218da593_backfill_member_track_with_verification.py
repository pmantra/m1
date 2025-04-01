"""backfill_member_track_with_verification

Revision ID: 033a218da593
Revises: bd7a33f2b109
Create Date: 2023-09-07 19:49:04.368085+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "033a218da593"
down_revision = "bd7a33f2b109"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    UPDATE maven.member_track mt INNER JOIN maven.backfill_verification_state bvs
    ON mt.user_id = bvs.user_id AND mt.organization_employee_id = bvs.organization_employee_id
    SET mt.eligibility_verification_id = bvs.backfill_verification_id
    WHERE mt.eligibility_verification_id IS NULL AND mt.eligibility_member_id IS NULL
    """
    )


def downgrade():
    # update the eligibility_verification_id back.
    # eligibility_verification_id is not in use, should be all null before back fill
    op.execute(
        """
    UPDATE maven.member_track mt SET mt.eligibility_verification_id = NULL 
    WHERE mt.eligibility_verification_id IS NOT NULL AND mt.eligibility_member_id IS NULL
        """
    )
