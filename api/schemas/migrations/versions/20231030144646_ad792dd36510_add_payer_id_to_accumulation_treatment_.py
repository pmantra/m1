"""add-payer-id-to-accumulation_treatment_mapping-table

Revision ID: ad792dd36510
Revises: 6ae1e553086d
Create Date: 2023-10-30 14:46:46.928833+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ad792dd36510"
down_revision = "6ae1e553086d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        ADD COLUMN `payer_id` BIGINT(20) NOT NULL,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        DROP COLUMN `payer_id`,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )
