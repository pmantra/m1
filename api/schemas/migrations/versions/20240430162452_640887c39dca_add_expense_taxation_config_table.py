"""add expense taxation config table

Revision ID: 640887c39dca
Revises: 914decf50888
Create Date: 2024-04-30 16:24:52.671289+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "640887c39dca"
down_revision = "914decf50888"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    CREATE TABLE IF NOT EXISTS `reimbursement_organization_settings_expense_types` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `reimbursement_organization_settings_id` bigint(20) NOT NULL,
    `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS', 'DONOR') COLLATE utf8mb4_unicode_ci NOT NULL,
    `taxation_status` enum('TAXABLE','NON_TAXABLE','ADOPTION_QUALIFIED','ADOPTION_NON_QUALIFIED','SPLIT_DX_INFERTILITY') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'TAXABLE',
    `reimbursement_method` enum('DIRECT_DEPOSIT','PAYROLL') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_organization_expense_type` (`reimbursement_organization_settings_id`, `expense_type`),
    CONSTRAINT `reimbursement_organization_settings_ibfk_4` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`) ON DELETE CASCADE
    );
    """
    op.execute(sql)


def downgrade():
    sql = """
    DROP TABLE IF EXISTS `reimbursement_organization_settings_expense_types`
    """
    op.execute(sql)
