"""member_health_plan_deprecate_is_family_plan

Revision ID: 3e2e9458f281
Revises: 40364268830b
Create Date: 2024-11-22 20:05:24.325336+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3e2e9458f281"
down_revision = "40364268830b"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `member_health_plan`
            CHANGE COLUMN `is_family_plan` `deprecated_is_family_plan` tinyint(1) DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `member_health_plan`
            CHANGE COLUMN `deprecated_is_family_plan` `is_family_plan` tinyint(1) DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
