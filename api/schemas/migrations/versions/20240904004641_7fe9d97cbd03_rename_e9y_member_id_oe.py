"""rename_e9y_member_id_oe

Revision ID: 7fe9d97cbd03
Revises: d7fd931edca3
Create Date: 2024-09-04 00:46:41.254293+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7fe9d97cbd03"
down_revision = "d7fd931edca3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE organization_employee 
        CHANGE COLUMN `new_eligibility_member_id` `eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE organization_employee 
        CHANGE COLUMN `eligibility_member_id` `new_eligibility_member_id` BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
