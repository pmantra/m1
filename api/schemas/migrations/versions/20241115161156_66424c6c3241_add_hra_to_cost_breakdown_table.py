"""add_hra_to_cost_breakdown_table

Revision ID: 66424c6c3241
Revises: 863b2a511604
Create Date: 2024-11-15 16:11:56.828130+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "66424c6c3241"
down_revision = "863b2a511604"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `cost_breakdown`
            ADD COLUMN `hra_applied` int(11) DEFAULT NULL after `oop_applied`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `cost_breakdown`
            DROP COLUMN `hra_applied`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)
