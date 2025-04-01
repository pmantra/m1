"""change_accumulation_report_filename_length

Revision ID: ac9bb5deae0f
Revises: 3a44444101a5
Create Date: 2024-10-24 17:51:43.826917+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ac9bb5deae0f"
down_revision = "3a44444101a5"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `payer_accumulation_reports`
        CHANGE COLUMN `filename` `filename` varchar(255) NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `payer_accumulation_reports`
        CHANGE COLUMN `filename` `filename` varchar(50) NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
