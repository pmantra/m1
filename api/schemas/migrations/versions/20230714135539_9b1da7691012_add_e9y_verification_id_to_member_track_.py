"""add_e9y_verification_id_to_member_track_table

Revision ID: 9b1da7691012
Revises: 3f882c51ab8c
Create Date: 2023-07-14 13:55:39.025951+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9b1da7691012"
down_revision = "3f882c51ab8c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.member_track
        ADD COLUMN eligibility_verification_id int(11) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.member_track
        DROP COLUMN eligibility_verification_id,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
