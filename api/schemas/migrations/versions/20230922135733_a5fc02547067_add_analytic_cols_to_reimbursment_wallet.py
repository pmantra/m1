"""add_analytic_cols_to_reimbursment_wallet

Revision ID: a5fc02547067
Revises: 27fb94ca8399
Create Date: 2023-09-22 13:57:33.144236+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a5fc02547067"
down_revision = "2bd5835beab9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_wallet
        ADD COLUMN initial_eligibility_member_id int(11) DEFAULT NULL,
        ADD COLUMN initial_eligibility_verification_id int(11) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_wallet
        DROP COLUMN initial_eligibility_member_id,
        DROP COLUMN initial_eligibility_verification_id,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
