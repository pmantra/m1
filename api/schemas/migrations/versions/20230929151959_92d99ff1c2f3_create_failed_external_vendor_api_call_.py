"""create_failed_external_vendor_api_call_table

Revision ID: 92d99ff1c2f3
Revises: 690f6242b8df
Create Date: 2023-09-29 15:19:59.882139+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "92d99ff1c2f3"
down_revision = "6ffebe90cccd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `failed_vendor_api_call` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT,
            `external_id` varchar(50) UNIQUE,
            `payload` text COLLATE utf8mb4_unicode_ci,
            `created_at` datetime NOT NULL,
            `modified_at` datetime NOT NULL,
            `called_by` varchar(30),
            `vendor_name` varchar(30),
            `api_name` varchar(30),
            `status` enum('pending','processed','failed') COLLATE utf8mb4_unicode_ci,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        CREATE INDEX `external_id_failed_vendor_api_call` ON failed_vendor_api_call(external_id);
        CREATE INDEX `modified_at_failed_vendor_api_call` ON failed_vendor_api_call(modified_at);
    """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS `external_id_failed_vendor_api_call`;
        DROP INDEX IF EXISTS `modified_at_failed_vendor_api_call`;
        DROP TABLE IF EXISTS `failed_vendor_api_call`;
        """
    )
