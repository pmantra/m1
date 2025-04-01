"""create_reschedule_history_table

Revision ID: c67f1e06e825
Revises: 75ff3988deaf
Create Date: 2023-08-30 21:35:45.123652+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c67f1e06e825"
down_revision = "75ff3988deaf"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `reschedule_history` (
            `appointment_id` int(11) NOT NULL,
            `scheduled_start` datetime NOT NULL,
            `scheduled_end` datetime NOT NULL,
            `created_at` datetime NOT NULL,
            KEY `appointment_id` (`appointment_id`),
            KEY `scheduled_start` (`scheduled_start`),
            KEY `scheduled_end` (`scheduled_end`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `reschedule_history`
        """
    )
