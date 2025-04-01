"""health_plan-end-at

Revision ID: a996e25565d4
Revises: 41de048712c0
Create Date: 2024-10-08 16:21:47.669523+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a996e25565d4"
down_revision = "41de048712c0"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    ALTER TABLE `member_health_plan`
    ADD COLUMN plan_end_at DATETIME DEFAULT NULL,
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
