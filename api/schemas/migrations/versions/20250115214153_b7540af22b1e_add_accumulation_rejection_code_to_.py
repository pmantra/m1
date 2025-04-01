"""Add accumulation rejection code to mapping

Revision ID: b7540af22b1e
Revises: 122b8d0d139c
Create Date: 2025-01-15 21:41:53.248889+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b7540af22b1e"
down_revision = "122b8d0d139c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        ADD COLUMN `response_code` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        DROP COLUMN `response_code`,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )
