"""add-needs-categories-table

Revision ID: 7632237e43f0
Revises: e41c0540ac87
Create Date: 2023-02-13 19:02:30.306689+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7632237e43f0"
down_revision = "e41c0540ac87"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `needs` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `name` VARCHAR(70) NOT NULL, 
            `description` VARCHAR(255) DEFAULT NULL, 
            `display_order` INT(11) DEFAULT NULL,
            `created_at` DATETIME DEFAULT NULL,
            `modified_at` DATETIME DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `needs_uq_1` (`name`)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `need_categories` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `name` VARCHAR(70) NOT NULL, 
            `description` VARCHAR(255) DEFAULT NULL, 
            `parent_category_id` INT(11) DEFAULT NULL, 
            `display_order` INT(11) DEFAULT NULL,
            `image_id` INT(11) DEFAULT NULL,
            `created_at` DATETIME DEFAULT NULL,
            `modified_at` DATETIME DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `need_categories_uq_1` (`name`),
            CONSTRAINT need_categories_ibfk_1 FOREIGN KEY (parent_category_id) REFERENCES need_categories(id),
            CONSTRAINT need_categories_ibfk_2 FOREIGN KEY (image_id) REFERENCES image(id)
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `needs`;")
    op.execute("DROP TABLE IF EXISTS `need_categories`;")
