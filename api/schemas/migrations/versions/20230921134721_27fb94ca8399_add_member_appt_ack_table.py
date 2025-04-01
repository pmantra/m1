"""add member_appt_ack table

Revision ID: 27fb94ca8399
Revises: 3a63d38e2676
Create Date: 2023-09-21 13:47:21.754797+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "27fb94ca8399"
down_revision = "3a63d38e2676"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `member_appointment_ack` (
            `modified_at` datetime DEFAULT NULL,
            `created_at` datetime DEFAULT NULL,
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `appointment_id` int(11) NOT NULL,
            `phone_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
            `user_id`  int(11) NOT NULL,
            `is_acked` tinyint(1) NOT NULL,
            `ack_date` datetime DEFAULT NULL,
            `confirm_message_sid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `reply_message_sid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `sms_sent_at` datetime DEFAULT NULL,
            PRIMARY KEY (`id`),
            KEY `appointment_id` (`appointment_id`),
            CONSTRAINT `appointment_fk` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`),
            KEY `user_id` (`user_id`),
            CONSTRAINT `user_fk` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `member_appointment_ack`;
        """
    )
