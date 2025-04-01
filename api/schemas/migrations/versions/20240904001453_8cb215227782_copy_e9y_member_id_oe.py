"""copy_e9y_member_id_oe

Revision ID: 8cb215227782
Revises: 85836ba62000
Create Date: 2024-09-04 00:14:53.482920+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8cb215227782"
down_revision = "85836ba62000"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE organization_employee set new_eligibility_member_id = eligibility_member_id 
        WHERE eligibility_member_id != 2147483647
        """
    )


def downgrade():
    op.execute(
        """
            UPDATE organization_employee set new_eligibility_member_id = NULL 
            """
    )
