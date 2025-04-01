"""add-e9y-v2-columns

Revision ID: 800cd46fff8f
Revises: e68ad96bbc45
Create Date: 2024-09-05 17:18:15.420054+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "800cd46fff8f"
down_revision = "5d33e2f8b496"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE organization_employee
        ADD COLUMN eligibility_member_2_id BIGINT DEFAULT NULL,
        ADD COLUMN eligibility_member_2_version INT DEFAULT NULL,
        ADD KEY idx_eligibility_member_2_id (eligibility_member_2_id),
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE organization_employee
        DROP INDEX idx_eligibility_member_2_id,
        DROP COLUMN eligibility_member_2_id,
        DROP COLUMN eligibility_member_2_version,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)
