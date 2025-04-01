"""add_treatment_accumulation_status_accepted

Revision ID: a3abe83fc80e
Revises: 1981613f7c66
Create Date: 2024-10-09 15:13:52.926993+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a3abe83fc80e"
down_revision = "1981613f7c66"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','REFUNDED','ROW_ERROR','PROCESSED','SUBMITTED','SKIP','REJECTED','ACCEPTED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=INPLACE, LOCK=NONE;        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `accumulation_treatment_mapping`
            MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','REFUNDED','ROW_ERROR','PROCESSED','SUBMITTED','SKIP','REJECTED') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)
