"""drop old employee health plan table

Revision ID: 4e4ba6f051a0
Revises: a2aab8ce095e
Create Date: 2023-08-22 15:16:39.535671+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4e4ba6f051a0"
down_revision = "a2aab8ce095e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DROP TABLE `employee_health_plan`;
        """
    )


def downgrade():
    op.execute(
        """
        CREATE TABLE `employee_health_plan` (
          `id` bigint(20) NOT NULL AUTO_INCREMENT,
          `employer_health_plan_id` bigint(20) DEFAULT NULL,
          `reimbursement_wallet_id` bigint(20) NOT NULL,
          `patient_first_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `patient_last_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `patient_plan_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `patient_date_of_birth` date NOT NULL,
          `subscriber_insurance_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `patient_insurance_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `plan_type` enum('GENERIC','HDHP') COLLATE utf8mb4_unicode_ci NOT NULL,
          `relation` enum('SELF','SPOUSE','PARTNER','DEPENDENT') COLLATE utf8mb4_unicode_ci NOT NULL,
          `created_at` datetime DEFAULT NULL,
          `modified_at` datetime DEFAULT NULL,
          `payer_id` bigint(20) NOT NULL,
          `subscriber_first_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
          `subscriber_last_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
          `subscriber_date_of_birth` date DEFAULT NULL,
          `is_family_plan` tinyint(1) NOT NULL,
          PRIMARY KEY (`id`),
          KEY `employer_health_plan_id` (`employer_health_plan_id`),
          KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
          KEY `employee_health_plan_ibfk_3` (`payer_id`),
          CONSTRAINT `employee_health_plan_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`),
          CONSTRAINT `employee_health_plan_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
          CONSTRAINT `employee_health_plan_ibfk_3` FOREIGN KEY (`payer_id`) REFERENCES `rte_payer_list` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )
