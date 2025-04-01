"""nuke_fully_covered_column

Revision ID: a10fcdbf3b4f
Revises: 37ae4729d600
Create Date: 2024-02-27 14:25:14.702684+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a10fcdbf3b4f"
down_revision = "37ae4729d600"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `member_health_plan`
        DROP COLUMN `fully_covered`,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `member_health_plan`
        ADD COLUMN `fully_covered` tinyint(1) DEFAULT '0',
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)
