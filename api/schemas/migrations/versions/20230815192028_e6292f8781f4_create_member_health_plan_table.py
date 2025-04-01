"""create member health plan table

Revision ID: e6292f8781f4
Revises: 2d90873b4135
Create Date: 2023-08-15 19:20:28.352275+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "e6292f8781f4"
down_revision = "2d90873b4135"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    CREATE TABLE `member_health_plan` (
      `id` bigint(20) NOT NULL AUTO_INCREMENT,
      `employer_health_plan_id` bigint(20) NOT NULL,
      `reimbursement_wallet_id` bigint(20) NOT NULL,
      `subscriber_insurance_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
      `is_subscriber` tinyint(1) NOT NULL DEFAULT 1,
      `subscriber_first_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `subscriber_last_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `subscriber_date_of_birth` date DEFAULT NULL,
      `member_date_of_birth` date DEFAULT NULL,
      `is_family_plan` tinyint(1) NOT NULL,
      `created_at` datetime DEFAULT NULL,
      `modified_at` datetime DEFAULT NULL,
      PRIMARY KEY (`id`),
      KEY `employer_health_plan_id` (`employer_health_plan_id`),
      KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
      CONSTRAINT `member_health_plan_ibfk_1` FOREIGN KEY (`employer_health_plan_id`) REFERENCES `employer_health_plan` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `member_health_plan_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
    );

    ALTER TABLE `rte_transaction` 
    DROP FOREIGN KEY `rte_transaction_ibfk_1`,
    CHANGE COLUMN `employee_health_plan_id` `member_health_plan_id` bigint(20) NOT NULL;

    DELETE FROM `employer_health_plan`;

    ALTER TABLE  `employer_health_plan` 
    ADD COLUMN `is_hdhp` tinyint(1) NOT NULL,
    ADD COLUMN `payer_id` bigint(20) NOT NULL,
    ADD KEY `employer_health_plan_ibfk_2` (`payer_id`),
    ADD CONSTRAINT `employer_health_plan_ibfk_2` FOREIGN KEY (`payer_id`) REFERENCES `rte_payer_list` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = """
    ALTER TABLE `employer_health_plan`
    DROP COLUMN `is_hdhp`,
    DROP COLUMN `payer_id`,
    DROP FOREIGN KEY employer_health_plan_ibfk_2;

    ALTER TABLE `rte_transaction`
    CHANGE COLUMN `member_health_plan_id` `employee_health_plan_id` bigint(20) NOT NULL,
    ADD CONSTRAINT `rte_transaction_ibfk_1` FOREIGN KEY (`employee_health_plan_id`) REFERENCES `employee_health_plan` (`id`);

    DROP TABLE IF EXISTS `member_health_plan`;
    """
    db.session.execute(query)
    db.session.commit()
