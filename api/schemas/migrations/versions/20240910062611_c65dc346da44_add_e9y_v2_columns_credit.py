"""add_e9y_v2_columns_credit

Revision ID: c65dc346da44
Revises: 800cd46fff8f
Create Date: 2024-09-10 06:26:11.331830+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c65dc346da44"
down_revision = "800cd46fff8f"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE credit
        ADD COLUMN eligibility_member_2_id BIGINT DEFAULT NULL,
        ADD COLUMN eligibility_member_2_version INT DEFAULT NULL,
        ADD COLUMN eligibility_verification_2_id BIGINT DEFAULT NULL,
        ADD KEY idx_eligibility_member_2_id (eligibility_member_2_id),
        ADD KEY idx_eligibility_verification_2_id (eligibility_verification_2_id),
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE credit
        DROP KEY idx_eligibility_member_2_id,
        DROP KEY idx_eligibility_verification_2_id,
        DROP COLUMN eligibility_member_2_id,
        DROP COLUMN eligibility_member_2_version,
        DROP COLUMN eligibility_verification_2_id,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)
