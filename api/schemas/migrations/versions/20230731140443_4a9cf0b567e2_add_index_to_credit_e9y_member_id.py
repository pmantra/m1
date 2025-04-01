"""add_index_to_credit_e9y_member_id

Revision ID: 4a9cf0b567e2
Revises: 5080a841650b
Create Date: 2023-07-31 14:04:43.420542+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4a9cf0b567e2"
down_revision = "5080a841650b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE credit
        ADD INDEX eligibility_member_id 
            (eligibility_member_id),
        ALGORITHM=INPLACE, LOCK=NONE
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE credit
        DROP INDEX eligibility_member_id,
        ALGORITHM=INPLACE, LOCK=NONE
    """
    )
