"""member_health_plan_add_plan_type

Revision ID: 77139469012c
Revises: 8de79bc5b0b1
Create Date: 2024-10-11 16:12:09.527264+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "77139469012c"
down_revision = "8de79bc5b0b1"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `member_health_plan`
            ADD COLUMN `plan_type` varchar(255) NOT NULL DEFAULT 'UNDETERMINED',
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `member_health_plan`
            DROP COLUMN `plan_type`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)
