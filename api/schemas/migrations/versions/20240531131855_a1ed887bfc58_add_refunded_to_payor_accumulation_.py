"""add_refunded_to_payor_accumulation_mapping_status

Revision ID: a1ed887bfc58
Revises: 61386b64c581
Create Date: 2024-05-31 13:18:55.979307+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1ed887bfc58"
down_revision = "61386b64c581"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','REFUNDED','ROW_ERROR','PROCESSED','SUBMITTED','SKIP','REJECTED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
                ALTER TABLE `accumulation_treatment_mapping`
                MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','ROW_ERROR','PROCESSED','SUBMITTED','SKIP','REJECTED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
                ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
