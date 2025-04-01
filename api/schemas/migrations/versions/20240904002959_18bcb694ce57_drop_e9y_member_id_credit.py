"""rename_e9y_member_id_credit

Revision ID: 18bcb694ce57
Revises: 688b9c7a650a
Create Date: 2024-09-04 00:29:59.880544+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "18bcb694ce57"
down_revision = "688b9c7a650a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE credit 
        CHANGE COLUMN `eligibility_member_id` `eligibility_member_id_deleted` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE credit 
        CHANGE COLUMN `eligibility_member_id_deleted` `eligibility_member_id` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
