"""drop_accumulator_status_col_from_bill

Revision ID: b164f0c1cbaa
Revises: 166cbf571101
Create Date: 2023-10-06 01:23:37.849125+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b164f0c1cbaa"
down_revision = "166cbf571101"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        DROP COLUMN `accumulator_status`,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        ADD COLUMN `accumulator_status` enum('NOT_PROCESSED','SENT','RECEIVED','ACCEPTED','REJECTED') 
        COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NOT_PROCESSED',
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
