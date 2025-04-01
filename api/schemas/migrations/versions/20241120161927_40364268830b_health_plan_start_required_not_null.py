"""health-plan-start-required-not-null

Revision ID: 40364268830b
Revises: bb85b3d3176e
Create Date: 2024-11-20 16:19:27.424395+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "40364268830b"
down_revision = "bb85b3d3176e"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    ALTER TABLE `member_health_plan`
    MODIFY COLUMN `plan_start_at` datetime NOT NULL;
    """
    op.execute(sql)


def downgrade():
    sql = """
    ALTER TABLE `member_health_plan`
    ALTER COLUMN `plan_start_at` DROP DEFAULT,
    ALGORITHM=COPY;
    """
    op.execute(sql)
