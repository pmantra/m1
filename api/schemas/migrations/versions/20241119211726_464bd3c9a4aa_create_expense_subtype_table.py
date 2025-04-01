"""Create expense subtype table

Revision ID: 464bd3c9a4aa
Revises: f9faf7e39648
Create Date: 2024-11-19 21:17:26.131406+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "464bd3c9a4aa"
down_revision = "f9faf7e39648"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `wallet_expense_subtype` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `expense_type` enum('FERTILITY','ADOPTION','EGG_FREEZING','SURROGACY','CHILDCARE','MATERNITY','MENOPAUSE','PRECONCEPTION_WELLNESS','DONOR','PRESERVATION') COLLATE utf8mb4_unicode_ci NOT NULL,
            `code` varchar(10) NOT NULL COLLATE utf8mb4_unicode_ci NOT NULL,
            `description` varchar(255) NOT NULL COLLATE utf8mb4_unicode_ci NOT NULL,
            `reimbursement_service_category_id` int(11) NOT NULL,
            `global_procedure_id` char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `reimbursement_service_category_id` (`reimbursement_service_category_id`),
            CONSTRAINT `wallet_expense_subtype_ibfk_1` FOREIGN KEY (`reimbursement_service_category_id`) REFERENCES `reimbursement_service_category` (`id`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `wallet_expense_subtype`;
        """
    )
