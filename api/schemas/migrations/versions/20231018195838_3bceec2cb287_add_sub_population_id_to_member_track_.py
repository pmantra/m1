"""add-sub-population-id-to-member-track-table

Revision ID: 3bceec2cb287
Revises: 8f752f16bffa
Create Date: 2023-10-18 19:58:38.826929+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3bceec2cb287"
down_revision = "8f752f16bffa"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_track`
        ADD COLUMN `sub_population_id` BIGINT DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_track`
        DROP COLUMN `sub_population_id`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
