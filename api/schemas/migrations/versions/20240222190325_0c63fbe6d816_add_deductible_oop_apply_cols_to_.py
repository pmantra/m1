"""add_deductible_oop_apply_cols_to_accumulation

Revision ID: 0c63fbe6d816
Revises: b2d50388f63b
Create Date: 2024-02-22 19:03:25.494577+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0c63fbe6d816"
down_revision = "b2d50388f63b"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `accumulation_treatment_mapping`
        ADD COLUMN `oop_applied` int(11) DEFAULT NULL AFTER `treatment_accumulation_status`,
        ADD COLUMN `deductible` int(11) DEFAULT NULL AFTER `treatment_accumulation_status`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `accumulation_treatment_mapping`
        DROP COLUMN `oop_applied`,
        DROP COLUMN `deductible`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)
