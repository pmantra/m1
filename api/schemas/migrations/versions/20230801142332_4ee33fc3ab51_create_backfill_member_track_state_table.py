"""create_backfill_member_track_state_table

Revision ID: 4ee33fc3ab51
Revises: c54d46d01d82
Create Date: 2023-08-01 14:23:32.168143+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4ee33fc3ab51"
down_revision = "dc4cbc21ac32"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `backfill_member_track_state` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `member_track_id` int(11) NOT NULL,
            `eligibility_member_id` int(11) DEFAULT NULL,
            PRIMARY KEY (`id`),
            KEY `member_track_id` (`member_track_id`),
            KEY `eligibility_member_id` (`eligibility_member_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;   
    """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `backfill_member_track_state`
    """
    )
