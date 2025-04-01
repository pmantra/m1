"""add_is_refund_to_accumulation_treatment_mapping

Revision ID: 06fea10feca6
Revises: 93f868016a97
Create Date: 2024-12-04 16:22:47.915108+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "06fea10feca6"
down_revision = "93f868016a97"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            ADD COLUMN `is_refund` bool DEFAULT FALSE,
            ALGORITHM=INPLACE, LOCK=NONE;        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            DROP COLUMN `is_refund`,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)
