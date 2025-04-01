"""Add_country_info_table

Revision ID: feb85e69b8b3
Revises: 4229047780f5
Create Date: 2022-10-24 16:52:52.181655+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "feb85e69b8b3"
down_revision = "4229047780f5"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `country_metadata` (
            `id` INT(11) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `country_code` CHAR(2) COLLATE utf8mb4_unicode_ci NOT NULL,
            `emoji` CHAR(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `ext_info_link` VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `summary` TEXT COLLATE utf8mb4_unicode_ci,
            `created_at` DATETIME DEFAULT NULL,
            `modified_at` DATETIME DEFAULT NULL,
            UNIQUE KEY `country_code` (`country_code`)
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `country_metadata`;")
