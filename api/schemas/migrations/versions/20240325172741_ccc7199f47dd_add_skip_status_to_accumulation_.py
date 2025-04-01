"""add_skip_status_to_accumulation_treatment_mapping

Revision ID: ccc7199f47dd
Revises: 300d305776f2
Create Date: 2024-03-25 17:27:41.614855+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ccc7199f47dd"
down_revision = "300d305776f2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','ROW_ERROR','PROCESSED','SUBMITTED','SKIP') COLLATE utf8mb4_unicode_ci DEFAULT NULL, 
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        MODIFY COLUMN `treatment_accumulation_status` enum('WAITING','PAID','ROW_ERROR','PROCESSED','SUBMITTED') COLLATE utf8mb4_unicode_ci DEFAULT NULL, 
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
