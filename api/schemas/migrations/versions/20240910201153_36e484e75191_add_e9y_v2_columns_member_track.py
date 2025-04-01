"""add_e9y_v2_columns_member_track

Revision ID: 36e484e75191
Revises: c65dc346da44
Create Date: 2024-09-10 20:11:53.536865+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "36e484e75191"
down_revision = "c65dc346da44"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE member_track
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
        ALTER TABLE member_track
        DROP KEY idx_eligibility_member_2_id,
        DROP KEY idx_eligibility_verification_2_id,
        DROP COLUMN eligibility_member_2_id,
        DROP COLUMN eligibility_member_2_version,
        DROP COLUMN eligibility_verification_2_id,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)
