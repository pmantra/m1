"""add_hra_to_employer_health_plan_table

Revision ID: 427da05f893c
Revises: 66424c6c3241
Create Date: 2024-11-15 16:35:42.509329+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "427da05f893c"
down_revision = "66424c6c3241"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            ADD COLUMN `hra_enabled` tinyint(1) NOT NULL DEFAULT '0',
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            DROP COLUMN `hra_enabled`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)
