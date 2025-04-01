"""add-foreign-key-schedule-event

Revision ID: 96fbac0c9cc4
Revises: 599ab9081a50
Create Date: 2024-03-28 22:58:11.027627+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "96fbac0c9cc4"
down_revision = "599ab9081a50"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `schedule_event`
        ADD COLUMN `schedule_recurring_block_id` bigint(20) DEFAULT NULL,
        ADD CONSTRAINT `schedule_event_ibfk_3`
        FOREIGN KEY (`schedule_recurring_block_id`)
            REFERENCES `schedule_recurring_block` (`id`)
            ON DELETE CASCADE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `schedule_event`
        DROP FOREIGN KEY `schedule_event_ibfk_3`,
        DROP COLUMN `schedule_recurring_block_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
