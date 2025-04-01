"""rename_e9y_member_id_mt

Revision ID: 1b83024dc95d
Revises: 51cbaa5c55b3
Create Date: 2024-09-04 00:46:56.568314+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1b83024dc95d"
down_revision = "51cbaa5c55b3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE member_track 
        CHANGE COLUMN `new_eligibility_member_id` `eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE member_track 
        CHANGE COLUMN `eligibility_member_id` `new_eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
