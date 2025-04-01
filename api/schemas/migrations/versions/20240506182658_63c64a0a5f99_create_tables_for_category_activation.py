"""create_tables_for_category_activation

Revision ID: 63c64a0a5f99
Revises: 56b23f91fc11
Create Date: 2024-05-06 18:26:58.916124+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "63c64a0a5f99"
down_revision = "56b23f91fc11"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        CREATE TABLE IF NOT EXISTS `reimbursement_organization_settings_allowed_category_rule` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT comment 'Internal unique ID',
            `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL comment 'External unique ID',
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP  comment 'The time at which this record was created',
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  comment 'The time at which this record was updated',
            `started_at`  datetime DEFAULT NULL comment 'The time from which this association is effective. Can be in the past, in the future or null. A null value or a future date implies this association is disabled',
            `reimbursement_organization_settings_allowed_category_id` bigint NOT NULL comment 'The ID of the reimbursement request allowed category',
            `rule_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL comment 'The name of the reimbursement request category rule',
            PRIMARY KEY (`id`),
            KEY `ix_allowed_category_rule_uuid` (`uuid`),
            KEY `ix_allowed_category_rule_name` (`rule_name`),
            CONSTRAINT `reimbursement_org_settings_allowed_category_rule_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_allowed_category_id`) REFERENCES `reimbursement_organization_settings_allowed_category` (`id`) ON DELETE CASCADE, 
            UNIQUE (`reimbursement_organization_settings_allowed_category_id`, `rule_name`)
    );
        CREATE TABLE IF NOT EXISTS `reimbursement_wallet_allowed_category_rules_evaluation_result` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT comment 'Internal unique ID',
            `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL comment 'External unique ID',
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP  comment 'The time at which this record was created.',
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  comment 'The time at which this record was updated',
            `reimbursement_organization_settings_allowed_category_id` bigint NOT NULL comment 'The ID of the reimbursement request allowed category',
            `reimbursement_wallet_id` bigint NOT NULL comment 'The ID of the reimbursement wallet',
            `executed_category_rule` text DEFAULT NULL comment 'All rules that returned True for this evaluation',
            `failed_category_rule` text DEFAULT NULL comment 'The rule that returned False upon evaluation. Null if the rule evaluated True',
            `evaluation_result` bool NOT NULL comment 'The result of the evaluated rule set',
            PRIMARY KEY (`id`),
            KEY `ix_allowed_category_result_uuid` (`uuid`),
            CONSTRAINT `reimbursement_org_settings_allowed_category_result_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_allowed_category_id`) REFERENCES `reimbursement_organization_settings_allowed_category` (`id`) ON DELETE CASCADE,
            CONSTRAINT `reimbursement_org_settings_allowed_category_result_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE,
            UNIQUE (`reimbursement_organization_settings_allowed_category_id`, `reimbursement_wallet_id`)
    );
        CREATE TABLE IF NOT EXISTS `reimbursement_wallet_allowed_category_settings` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT comment 'Internal unique ID',
            `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL comment 'External unique ID',
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP  comment 'The time at which this record was created.',
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  comment 'The time at which this record was updated',
            `updated_by` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL comment 'User that last updated this record',
            `reimbursement_organization_settings_allowed_category_id` bigint NOT NULL comment 'The ID of the reimbursement request allowed category',
            `reimbursement_wallet_id` bigint NOT NULL comment 'The ID of the reimbursement wallet',
            `access_level` enum('FULL_ACCESS', 'NO_ACCESS') COLLATE utf8mb4_unicode_ci NOT NULL comment 'The access of the evaluated rule',
            `access_level_source` enum('RULES', 'OVERRIDE', 'NO_RULES') COLLATE utf8mb4_unicode_ci NOT NULL comment 'The rule evaluation setting source',
            PRIMARY KEY (`id`),
            KEY `ix_allowed_category_settings_uuid` (`uuid`),
            CONSTRAINT `reimbursement_org_settings_allowed_category_settings_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_allowed_category_id`) REFERENCES `reimbursement_organization_settings_allowed_category` (`id`) ON DELETE CASCADE,
            CONSTRAINT `reimbursement_org_settings_allowed_category_settings_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE,
            UNIQUE (`reimbursement_organization_settings_allowed_category_id`, `reimbursement_wallet_id`)
    );
    """
    op.execute(sql)


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `reimbursement_wallet_allowed_category_settings`;
        DROP TABLE IF EXISTS `reimbursement_wallet_allowed_category_rules_evaluation_result`;
        DROP TABLE IF EXISTS `reimbursement_organization_settings_allowed_category_rule`;
        """
    )
