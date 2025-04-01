"""backfill_member_track_table

Revision ID: 1088e6a98f3d
Revises: 581cac6ac9bf
Create Date: 2023-08-01 20:27:21.649374+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1088e6a98f3d"
down_revision = "581cac6ac9bf"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    UPDATE maven.member_track mt
    INNER JOIN maven.backfill_member_track_state bmts on bmts.member_track_id = mt.id
        SET mt.eligibility_member_id = bmts.eligibility_member_id
    """
    )


def downgrade():
    op.execute(
        """
    UPDATE maven.member_track mt
    INNER JOIN maven.backfill_member_track_state bmts on bmts.member_track_id = mt.id
        SET mt.eligibility_member_id = NULL
    """
    )
