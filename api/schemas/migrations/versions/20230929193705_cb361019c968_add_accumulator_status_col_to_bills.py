"""add_accumulator_status_col_to_bills

Revision ID: cb361019c968
Revises: b48f4a5f34a3
Create Date: 2023-09-29 19:37:05.670900+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "cb361019c968"
down_revision = "b48f4a5f34a3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        ADD COLUMN `accumulator_status` enum('NOT_PROCESSED','SENT','RECEIVED','ACCEPTED','REJECTED') 
        COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NOT_PROCESSED',
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        DROP COLUMN `accumulator_status`,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
