"""copy_e9y_member_id_credit

Revision ID: c29e6fd011f6
Revises: 8cb215227782
Create Date: 2024-09-04 00:15:03.592404+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c29e6fd011f6"
down_revision = "8cb215227782"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE credit set new_eligibility_member_id = eligibility_member_id 
        WHERE eligibility_member_id != 2147483647
        """
    )


def downgrade():
    op.execute(
        """
            UPDATE credit set new_eligibility_member_id = NULL 
            """
    )
