"""add action and member_track_id to incentive-fulfillment table

Revision ID: e24dc1396354
Revises: 7af2f5fff25a
Create Date: 2023-11-01 21:22:58.872127+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e24dc1396354"
down_revision = "7af2f5fff25a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `incentive_fulfillment`
        DROP COLUMN `user_id`,
        ADD COLUMN `incentivized_action` enum('CA_INTRO', 'OFFBOARDING_ASSESSMENT') NOT NULL,
        ADD COLUMN `member_track_id` VARCHAR(120) NOT NULL,
        ADD CONSTRAINT `incentive_fulfillment_uq_1` UNIQUE (incentivized_action, member_track_id),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `incentive_fulfillment`
        DROP INDEX `incentive_fulfillment_uq_1`,
        DROP COLUMN `incentivized_action`,
        DROP COLUMN `member_track_id`,
        ADD COLUMN `user_id` bigint(20) NOT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
