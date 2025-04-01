"""add_modified_by_and_change_reason

Revision ID: b9e85cc68b7d
Revises: ab4401dae419
Create Date: 2023-12-01 17:06:01.549673+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b9e85cc68b7d"
down_revision = "ab4401dae419"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_track`
        ADD COLUMN `modified_by` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN `change_reason` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_track`
        DROP COLUMN `modified_by`,
        DROP COLUMN `change_reason`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
