"""change response code type on accumulation treatment mapping

Revision ID: 29d361670908
Revises: 689f29514e8e
Create Date: 2025-03-12 14:56:47.275259+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "29d361670908"
down_revision = "689f29514e8e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        MODIFY COLUMN `response_code` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=COPY, 
        LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        MODIFY COLUMN `response_code` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=COPY, 
        LOCK=SHARED;
        """
    )
