"""rename_e9y_member_id_rw

Revision ID: d7fd931edca3
Revises: b1788111d309
Create Date: 2024-09-04 00:30:13.967473+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d7fd931edca3"
down_revision = "b1788111d309"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_wallet 
        CHANGE COLUMN `initial_eligibility_member_id` `initial_eligibility_member_id_deleted` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_wallet 
        CHANGE COLUMN `initial_eligibility_member_id_deleted` `initial_eligibility_member_id` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
