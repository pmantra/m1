"""rename_e9y_member_id_credit

Revision ID: 51cbaa5c55b3
Revises: 7fe9d97cbd03
Create Date: 2024-09-04 00:46:48.688829+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "51cbaa5c55b3"
down_revision = "7fe9d97cbd03"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE credit 
        CHANGE COLUMN `new_eligibility_member_id` `eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE credit 
        CHANGE COLUMN `eligibility_member_id` `new_eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
