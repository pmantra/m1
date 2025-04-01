"""Add treatment accumulation status 'REJECTED'

Revision ID: 0c0e64596a1d
Revises: 96fbac0c9cc4
Create Date: 2024-04-02 19:18:10.102652+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0c0e64596a1d"
down_revision = "dc699a052c47"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','ROW_ERROR','PROCESSED','SUBMITTED', 'SKIP', 'REJECTED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
                ALTER TABLE `accumulation_treatment_mapping`
                MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','ROW_ERROR','PROCESSED','SUBMITTED', 'SKIP') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
