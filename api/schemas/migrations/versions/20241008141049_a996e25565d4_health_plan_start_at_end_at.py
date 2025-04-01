"""health_plan-start-at-end-at

Revision ID: 41de048712c0
Revises: 8aa0fa31c6e5
Create Date: 2024-10-08 14:10:49.135033+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "41de048712c0"
down_revision = "8aa0fa31c6e5"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    ALTER TABLE `member_health_plan`
    ADD COLUMN plan_start_at DATETIME DEFAULT NULL,
    ALGORITHM=COPY;
    """
    op.execute(sql)


def downgrade():
    sql = """
    ALTER TABLE `member_health_plan`
    DROP COLUMN plan_end_at,
    ALGORITHM=COPY;
    """
    op.execute(sql)
