"""add-eligibility-member-id-to-member-track

Revision ID: 332226e2314d
Revises: 9ee150d5d5df
Create Date: 2023-05-31 18:16:23.710449+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "332226e2314d"
down_revision = "9ee150d5d5df"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.member_track
        ADD COLUMN eligibility_member_id int(11) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.member_track
        DROP COLUMN eligibility_member_id,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
