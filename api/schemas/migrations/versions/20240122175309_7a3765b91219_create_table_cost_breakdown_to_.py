"""create_table_cost_breakdown_to_reimbursement_request

Revision ID: 7a3765b91219
Revises: 2e2363803701
Create Date: 2024-01-22 17:53:09.147063+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7a3765b91219"
down_revision = "2e2363803701"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
      CREATE TABLE `reimbursement_request_to_cost_breakdown` (
          `id` bigint(20) NOT NULL,
          `reimbursement_request_id` bigint(20) UNIQUE NOT NULL,
          `cost_breakdown_id` bigint(20) NOT NULL,
          `claim_type` enum('EMPLOYER','EMPLOYEE_DEDUCTIBLE') COLLATE utf8mb4_unicode_ci NOT NULL,
          `treatment_procedure_uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
          `created_at` datetime NOT NULL,
          `modified_at` datetime NOT NULL,
          PRIMARY KEY (`id`),
          KEY `reimbursement_request_id_key` (`reimbursement_request_id`),
          KEY `cost_breakdown_id_key` (`cost_breakdown_id`),
          KEY `treatment_procedure_uuid_key` (`treatment_procedure_uuid`),
          CONSTRAINT `reimbursement_request_to_cost_breakdown_ibfk_1` FOREIGN KEY (`cost_breakdown_id`) REFERENCES `cost_breakdown` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
          CONSTRAINT `reimbursement_request_to_cost_breakdown_ibfk_2` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `reimbursement_request_to_cost_breakdown`;
        """
    )
