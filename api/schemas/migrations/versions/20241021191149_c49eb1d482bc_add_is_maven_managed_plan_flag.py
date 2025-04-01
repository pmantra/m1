"""add_is_maven_managed_plan_flag

Revision ID: c49eb1d482bc
Revises: b0c16254f55c
Create Date: 2024-10-21 19:11:49.882359+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c49eb1d482bc"
down_revision = "b0c16254f55c"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            ADD COLUMN `is_maven_managed_plan` tinyint(1) NOT NULL DEFAULT '0',
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            DROP COLUMN `is_maven_managed_plan`,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
