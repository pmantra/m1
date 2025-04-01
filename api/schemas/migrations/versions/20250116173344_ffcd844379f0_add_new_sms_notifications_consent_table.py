"""add new sms notifications consent table

Revision ID: ffcd844379f0
Revises: 8a1fbe627aba
Create Date: 2025-01-16 17:33:44.427219+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "ffcd844379f0"
down_revision = "8a1fbe627aba"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `sms_notifications_consent` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `user_id` BIGINT(11) NOT NULL,
        `sms_messaging_notifications_enabled` BOOL NOT NULL DEFAULT FALSE,
        `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `user_id` (`user_id`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE `sms_notifications_consent`;
        """
    )
