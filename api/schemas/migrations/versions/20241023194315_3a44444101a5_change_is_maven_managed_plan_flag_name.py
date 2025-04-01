"""change_is_maven_managed_plan_flag_name

Revision ID: 3a44444101a5
Revises: f0212045d8e7
Create Date: 2024-10-23 19:43:15.057789+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3a44444101a5"
down_revision = "f0212045d8e7"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            CHANGE COLUMN `is_maven_managed_plan` `is_payer_integrated` tinyint(1) NOT NULL DEFAULT '0',
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            CHANGE COLUMN `is_payer_integrated` `is_maven_managed_plan` tinyint(1) NOT NULL DEFAULT '0',
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
