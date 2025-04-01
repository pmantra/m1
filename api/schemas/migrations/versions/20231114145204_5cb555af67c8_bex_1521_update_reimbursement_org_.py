"""BEX-1521-update-reimbursement-org-setting

Revision ID: 5cb555af67c8
Revises: 586a13668149
Create Date: 2023-11-14 14:52:04.065994+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5cb555af67c8"
down_revision = "586a13668149"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `reimbursement_organization_settings_require_procedures` (
           `id` bigint NOT NULL,
           `reimbursement_org_settings_id` bigint(20) NOT NULL,
           `global_procedure_id` varchar(36),
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY `reimbursement_org_settings_id` (`reimbursement_org_settings_id`),
            PRIMARY KEY (`id`)
        )
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `reimbursement_organization_settings_require_procedures`
        """
    )
