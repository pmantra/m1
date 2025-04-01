"""add-schedule-recurring-block

Revision ID: 599ab9081a50
Revises: fc38a0c8003d
Create Date: 2024-03-27 19:41:25.382262+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "599ab9081a50"
down_revision = "fc38a0c8003d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `schedule_recurring_block` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT,
            `starts_at` datetime NOT NULL,
            `ends_at` datetime NOT NULL,
            `frequency` enum('MONTHLY','WEEKLY','DAILY') COLLATE utf8mb4_unicode_ci NOT NULL,
            `until` datetime DEFAULT NULL,
            `latest_date_events_created` datetime DEFAULT NULL,
            `schedule_id` int(11) DEFAULT NULL,
            `created_at` DATETIME DEFAULT NULL,
            `modified_at` DATETIME DEFAULT NULL,
            PRIMARY KEY (`id`),
            INDEX `ix_schedule_id` (`schedule_id`),
            CONSTRAINT `schedule_recurring_block_ibfk_1` FOREIGN KEY (`schedule_id`)
                REFERENCES `schedule`(`id`)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS `schedule_recurring_block_weekday_index` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT,
            `schedule_recurring_block_id` bigint(20) NOT NULL,
            `week_days_index` int(11) DEFAULT NULL,
            PRIMARY KEY (`id`),
            INDEX `ix_schedule_recurring_block_id` (`schedule_recurring_block_id`),
            CONSTRAINT `schedule_recurring_block_weekday_index_ibfk_1` FOREIGN KEY (`schedule_recurring_block_id`)
                REFERENCES `schedule_recurring_block`(`id`)
                ON DELETE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `schedule_recurring_block_weekday_index` CASCADE;
        DROP TABLE IF EXISTS `schedule_recurring_block` CASCADE;
        """
    )
