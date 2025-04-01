"""rename_e9y_member_id_rw

Revision ID: bb6463398c4a
Revises: 1b83024dc95d
Create Date: 2024-09-04 00:47:03.212013+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "bb6463398c4a"
down_revision = "1b83024dc95d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_wallet 
        CHANGE COLUMN `new_eligibility_member_id` `initial_eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_wallet 
        CHANGE COLUMN `initial_eligibility_member_id` `new_eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
