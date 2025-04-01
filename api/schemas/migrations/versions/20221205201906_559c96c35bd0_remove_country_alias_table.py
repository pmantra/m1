"""remove_country_alias_table

Revision ID: 559c96c35bd0
Revises: efb1979be9c7
Create Date: 2022-12-05 20:19:06.839003+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "559c96c35bd0"
down_revision = "efb1979be9c7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS `country_alias`")


def downgrade():
    op.execute(
        """
        CREATE TABLE `country_alias` (
            `id` bigint(20) NOT NULL,
            `alias` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
            `country_id` int(11) NOT NULL,
            `created_at` datetime DEFAULT NULL,
            `modified_at` datetime DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `country_alias_uq_1` (`alias`),
            KEY `country_alias_ibfk_1` (`country_id`),
            CONSTRAINT `country_alias_ibfk_1` FOREIGN KEY (`country_id`) REFERENCES `country` (`id`)
        ) 
        """
    )
