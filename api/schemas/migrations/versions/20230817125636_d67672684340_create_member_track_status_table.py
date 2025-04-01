"""create_member_track_status_table

Revision ID: d67672684340
Revises: c1079d1ee4a2
Create Date: 2023-08-17 12:56:36.019330+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d67672684340"
down_revision = "c1079d1ee4a2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `member_track_status` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `member_track_id` int(11) NOT NULL,
            `status` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `member_track_id` (`member_track_id`)
        );
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `member_track_status`;")
