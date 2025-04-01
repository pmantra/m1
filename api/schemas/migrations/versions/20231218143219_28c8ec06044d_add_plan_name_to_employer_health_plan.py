"""add_plan_name_to_employer_health_plan

Revision ID: 28c8ec06044d
Revises: b1a3a1fd225d
Create Date: 2023-12-18 14:32:19.336391+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "28c8ec06044d"
down_revision = "b1a3a1fd225d"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `name` varchar(128) DEFAULT NULL after `id`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `name`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)
