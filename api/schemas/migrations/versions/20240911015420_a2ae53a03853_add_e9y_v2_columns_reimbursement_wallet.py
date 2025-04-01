"""add_e9y_v2_columns_reimbursement_wallet

Revision ID: a2ae53a03853
Revises: 36e484e75191
Create Date: 2024-09-11 01:54:20.400637+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a2ae53a03853"
down_revision = "36e484e75191"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE reimbursement_wallet
        ADD COLUMN initial_eligibility_member_2_id BIGINT DEFAULT NULL,
        ADD COLUMN initial_eligibility_member_2_version INT DEFAULT NULL,
        ADD COLUMN initial_eligibility_verification_2_id BIGINT DEFAULT NULL,
        ADD KEY idx_initial_eligibility_member_2_id (initial_eligibility_member_2_id),
        ADD KEY idx_initial_eligibility_verification_2_id (initial_eligibility_verification_2_id),
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE reimbursement_wallet
        DROP KEY idx_initial_eligibility_member_2_id,
        DROP KEY idx_initial_eligibility_verification_2_id,
        DROP COLUMN initial_eligibility_member_2_id,
        DROP COLUMN initial_eligibility_member_2_version,
        DROP COLUMN initial_eligibility_verification_2_id,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)
