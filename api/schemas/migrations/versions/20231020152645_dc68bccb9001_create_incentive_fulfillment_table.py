"""create incentive-fulfillment table

Revision ID: dc68bccb9001
Revises: 40399bb85f5d
Create Date: 2023-10-20 15:26:45.729374+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "dc68bccb9001"
down_revision = "40399bb85f5d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `incentive_fulfillment` (
            `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `user_id` bigint(20) NOT NULL,
            `incentive_id` int(11) NOT NULL,
            `status` enum('SEEN', 'EARNED', 'PROCESSING', 'FULFILLED') NOT NULL,
            `tracking_number` VARCHAR(120),
            `date_seen` datetime,
            `date_earned` datetime,
            `date_issued` datetime,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY (user_id),
            FOREIGN KEY (incentive_id)
                REFERENCES `incentive`(`id`)
                ON DELETE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `incentive_fulfillment`;
        """
    )
