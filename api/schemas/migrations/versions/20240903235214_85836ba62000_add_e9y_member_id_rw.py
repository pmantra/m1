"""add_e9y_member_id_rw

Revision ID: 85836ba62000
Revises: e759604e4726
Create Date: 2024-09-03 23:52:14.427153+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "85836ba62000"
down_revision = "e759604e4726"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_wallet ADD COLUMN new_eligibility_member_id BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
            ALTER TABLE reimbursement_wallet DROP COLUMN new_eligibility_member_id,
            ALGORITHM=INPLACE,
            LOCK=NONE;
            """
    )
