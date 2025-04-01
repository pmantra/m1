"""create_new_wallet_report_configuration_tables

Revision ID: a27b7dd7443c
Revises: 0c0e64596a1d
Create Date: 2024-04-11 13:19:55.775399+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a27b7dd7443c"
down_revision = "0c0e64596a1d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `wallet_client_report_configuration_v2` (
          `id` int(11) NOT NULL AUTO_INCREMENT,
          `cadence` enum('WEEKLY','BIWEEKLY','MONTHLY') NOT NULL,
          `organization_id` int(11) NOT NULL,
          PRIMARY KEY (`id`),
          KEY `organization_id` (`organization_id`)
        );
        
        CREATE TABLE `wallet_client_report_configuration_report_columns_v2` (
          `wallet_client_report_configuration_report_type_id` int(11) NOT NULL,
          `wallet_client_report_configuration_id` int(11) NOT NULL,
          FOREIGN KEY (`wallet_client_report_configuration_report_type_id`) REFERENCES `wallet_client_report_configuration_report_types` (`id`),
          FOREIGN KEY (`wallet_client_report_configuration_id`) REFERENCES `wallet_client_report_configuration_v2` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );

        CREATE TABLE `wallet_client_report_configuration_filter` (
          `id` int(11) NOT NULL AUTO_INCREMENT,
          `configuration_id` int(11) NOT NULL,
          `filter_type` enum('PRIMARY_EXPENSE_TYPE','COUNTRY') COLLATE utf8mb4_unicode_ci NOT NULL,
          `filter_value` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `equal` tinyint(1) DEFAULT '1',
          PRIMARY KEY (`id`),
          FOREIGN KEY (`configuration_id`) REFERENCES `wallet_client_report_configuration_v2` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        
        ALTER TABLE `wallet_client_reports`
        ADD COLUMN `configuration_id` int(11) DEFAULT NULL after `organization_id`,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `wallet_client_reports`
        DROP COLUMN `configuration_id`,
        ALGORITHM=COPY, LOCK=SHARED;
        DROP TABLE IF EXISTS `wallet_client_report_configuration_filter`;
        DROP TABLE IF EXISTS `wallet_client_report_configuration_report_columns_v2`;
        DROP TABLE IF EXISTS `wallet_client_report_configuration_v2`;
        """
    )
