"""health-plan-start-required

Revision ID: a7a360957be9
Revises: ac9bb5deae0f
Create Date: 2024-10-28 13:41:27.874107+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a7a360957be9"
down_revision = "ac9bb5deae0f"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    ALTER TABLE `member_health_plan`
    ALTER COLUMN `plan_start_at` DROP DEFAULT,
    ALGORITHM=COPY;
    """
    op.execute(sql)


def downgrade():
    sql = """
    ALTER TABLE `member_health_plan`
    ALTER COLUMN `plan_start_at` SET DEFAULT NULL,
    ALGORITHM=COPY;
    """
    op.execute(sql)
