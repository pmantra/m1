"""Add global procedure exclusions for Wallet organization settings

Revision ID: 40d684548a12
Revises: e6f81ff574bc
Create Date: 2023-07-20 21:39:19.992601+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "40d684548a12"
down_revision = "e6f81ff574bc"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    CREATE TABLE `reimbursement_organization_settings_excluded_procedures` (
    `reimbursement_organization_settings_id` bigint(20) NOT NULL,
    `global_procedure_id` bigint(20) NOT NULL,
    `created_at` datetime NOT NULL,
    `modified_at` datetime NOT NULL,
    PRIMARY KEY (`reimbursement_organization_settings_id`,`global_procedure_id`),
    CONSTRAINT `reimbursement_organization_settings_excluded_procedures_ibfk_1` FOREIGN KEY (`reimbursement_organization_settings_id`) REFERENCES `reimbursement_organization_settings` (`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = "DROP TABLE IF EXISTS `reimbursement_organization_settings_excluded_procedures`;"
    db.session.execute(query)
    db.session.commit()
