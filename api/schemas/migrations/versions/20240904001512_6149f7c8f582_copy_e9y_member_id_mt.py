"""copy_e9y_member_id_mt

Revision ID: 6149f7c8f582
Revises: c29e6fd011f6
Create Date: 2024-09-04 00:15:12.714722+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6149f7c8f582"
down_revision = "c29e6fd011f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE member_track set new_eligibility_member_id = eligibility_member_id 
        WHERE eligibility_member_id != 2147483647
        """
    )


def downgrade():
    op.execute(
        """
            UPDATE member_track set new_eligibility_member_id = NULL 
            """
    )
