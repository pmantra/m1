"""add_category_rule_evaluation_failure_table

Revision ID: 8a1fbe627aba
Revises: 5d2a426b53e1
Create Date: 2025-01-16 18:51:06.978850+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8a1fbe627aba"
down_revision = "5d2a426b53e1"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    CREATE TABLE IF NOT EXISTS `reimbursement_wallet_allowed_category_rule_evaluation_failure` (
        `id` BIGINT(20) NOT NULL AUTO_INCREMENT,
        `uuid` VARCHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
        `rule_name` VARCHAR(128) COLLATE utf8mb4_unicode_ci NOT NULL,
        `evaluation_result_id` BIGINT(20) NOT NULL,
        `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `modified_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `idx_evaluation_result_id` (`evaluation_result_id`),
        KEY `idx_evaluation_result_uuid` (`uuid`),
        CONSTRAINT `evaluation_result_ibfk_1` FOREIGN KEY (`evaluation_result_id`) REFERENCES `reimbursement_wallet_allowed_category_rules_evaluation_result` (`id`) ON DELETE CASCADE,
        UNIQUE (`evaluation_result_id`, `rule_name`)
    );
    """
    op.execute(sql)


def downgrade():
    sql = """
    DROP TABLE IF EXISTS `reimbursement_wallet_allowed_category_rule_evaluation_failure`;
    """
    op.execute(sql)
