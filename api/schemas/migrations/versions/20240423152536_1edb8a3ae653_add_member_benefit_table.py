"""add_member_benefit_table

Revision ID: 1edb8a3ae653
Revises: f8dc11ec225d
Create Date: 2024-04-23 15:25:36.994365+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1edb8a3ae653"
down_revision = "f8dc11ec225d"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    CREATE TABLE IF NOT EXISTS `member_benefit` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `user_id` int(11) NOT NULL,
    `benefit_id` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
    `started_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `user_id` (`user_id`),
    UNIQUE KEY `benefit_id` (`benefit_id`),
    CONSTRAINT `member_benefit_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
    );
    """
    op.execute(sql)


def downgrade():
    sql = """
    DROP TABLE IF EXISTS `member_benefit`
    """
    op.execute(sql)
