"""copy_e9y_member_id_rw

Revision ID: fa47b10bd297
Revises: 6149f7c8f582
Create Date: 2024-09-04 00:15:22.126538+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "fa47b10bd297"
down_revision = "6149f7c8f582"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE reimbursement_wallet set new_eligibility_member_id = initial_eligibility_member_id 
        WHERE initial_eligibility_member_id != 2147483647
        """
    )


def downgrade():
    op.execute(
        """
            UPDATE reimbursement_wallet set new_eligibility_member_id = NULL 
            """
    )
