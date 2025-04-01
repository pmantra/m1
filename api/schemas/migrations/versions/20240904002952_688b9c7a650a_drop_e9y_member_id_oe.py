"""rename_e9y_member_id_oe

Revision ID: 688b9c7a650a
Revises: fa47b10bd297
Create Date: 2024-09-04 00:29:52.701179+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "688b9c7a650a"
down_revision = "fa47b10bd297"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE organization_employee 
        CHANGE COLUMN `eligibility_member_id` `eligibility_member_id_deleted` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE organization_employee 
        CHANGE COLUMN `eligibility_member_id_deleted` `eligibility_member_id` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
