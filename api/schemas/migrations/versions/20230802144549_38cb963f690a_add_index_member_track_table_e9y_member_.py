"""add_index_member_track_table_e9y_member_id

Revision ID: 38cb963f690a
Revises: 1088e6a98f3d
Create Date: 2023-08-02 14:45:49.765608+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "38cb963f690a"
down_revision = "7c390b7cf4ec"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE member_track
        ADD INDEX eligibility_member_id 
            (eligibility_member_id),
        ALGORITHM=INPLACE, LOCK=NONE
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE member_track
        DROP INDEX eligibility_member_id,
        ALGORITHM=INPLACE, LOCK=NONE
    """
    )
