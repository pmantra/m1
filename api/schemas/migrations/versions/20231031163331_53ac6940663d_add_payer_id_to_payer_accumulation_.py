"""add_payer_id_to_payer_accumulation_reports

Revision ID: 53ac6940663d
Revises: f2b18d9dc43b
Create Date: 2023-10-31 16:33:31.690337+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "53ac6940663d"
down_revision = "f2b18d9dc43b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `payer_accumulation_reports`
        DROP COLUMN `payer`,
        ADD COLUMN `payer_id` BIGINT(20) NOT NULL after `id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `payer_accumulation_reports`
        DROP COLUMN `payer_id`,
        ADD COLUMN `payer` enum('UHC', 'CIGNA', 'ESI', 'OHIO_HEALTH'),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
