"""create-tables-for-abfe

Revision ID: 6d925a992ab9
Revises: 995a741a1d45
Create Date: 2023-09-12 18:50:54.017359+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6d925a992ab9"
down_revision = "995a741a1d45"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `criterion_value` (
            `id` bigint NOT NULL AUTO_INCREMENT,
            `organization_id` bigint NOT NULL,
            `criterion_field` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
            `criterion_value` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY (`organization_id`, `criterion_field`), 
            UNIQUE (`organization_id`, `criterion_field`, `criterion_value`)
        );
        CREATE TABLE IF NOT EXISTS `feature_set` (
            `id` bigint NOT NULL AUTO_INCREMENT,
            `organization_id` int(11) NOT NULL,
            `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY (`organization_id`),
            UNIQUE (`organization_id`, `name`)
        );
        CREATE TABLE IF NOT EXISTS `feature_type` (
            `id` bigint NOT NULL AUTO_INCREMENT,
            `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
            `enum_id` bigint NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE(`enum_id`)
        );
        CREATE TABLE IF NOT EXISTS `feature` (
            `id` bigint NOT NULL AUTO_INCREMENT,
            `feature_set_id` bigint NOT NULL,
            `feature_type_enum_id` bigint NOT NULL,
            `feature_id` bigint NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY (`feature_type_enum_id`), 
            UNIQUE (`feature_set_id`, `feature_type_enum_id`, `feature_id`),
            CONSTRAINT `feature_feature_set_fk` FOREIGN KEY (`feature_set_id`) 
                REFERENCES `feature_set` (`id`) ON DELETE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `feature` CASCADE ;
        DROP TABLE IF EXISTS `feature_type` CASCADE ;
        DROP TABLE IF EXISTS `feature_set` CASCADE ;
        DROP TABLE IF EXISTS `criterion_value` CASCADE ;
        """
    )
