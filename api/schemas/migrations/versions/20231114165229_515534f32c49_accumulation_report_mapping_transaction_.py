"""accumulation_report_mapping_transaction_id

Revision ID: 515534f32c49
Revises: 5cb555af67c8
Create Date: 2023-11-14 16:52:29.950448+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "515534f32c49"
down_revision = "5cb555af67c8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        ADD COLUMN `accumulation_transaction_id` VARCHAR(255) after `id`,
        DROP COLUMN `accumulation_uuid`,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        ADD COLUMN `accumulation_uuid` VARCHAR(36) after `id`,
        DROP COLUMN `accumulation_transaction_id`,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
