"""add_hra_applied_to_accumulation_mapping_table

Revision ID: 4bcaea3f8578
Revises: 427da05f893c
Create Date: 2024-11-15 16:59:15.342300+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4bcaea3f8578"
down_revision = "427da05f893c"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            ADD COLUMN `hra_applied` int(11) DEFAULT NULL after `oop_applied`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            DROP COLUMN `hra_applied`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)
