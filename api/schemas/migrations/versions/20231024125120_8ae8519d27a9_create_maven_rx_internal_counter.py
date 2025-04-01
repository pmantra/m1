"""create_maven_rx_internal_counter

Revision ID: 8ae8519d27a9
Revises: c2c8336aa03b
Create Date: 2023-10-24 12:51:20.521911+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8ae8519d27a9"
down_revision = "c2c8336aa03b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `health_plan_year_to_date_spend` CASCADE;
        
        CREATE TABLE IF NOT EXISTS `health_plan_year_to_date_spend` (
            `id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `policy_id` varchar(50) NOT NULL,
            `first_name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
            `last_name` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
            `year` int NOT NULL,
            `source` enum('MAVEN', 'ESI') default 'MAVEN',
            `plan_type` enum('INDIVIDUAL', 'FAMILY') default 'INDIVIDUAL',
            `deductible_applied_amount` int default 0,
            `oop_applied_amount` int default 0,
            `bill_id` bigint(20) default NULL,
            `transmission_id` varchar(50) default NULL,
            `transaction_filename` varchar(50) default NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY `patient` (`policy_id`,`first_name`, `last_name`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `health_plan_year_to_date_spend` CASCADE;
        
        CREATE TABLE IF NOT EXISTS `health_plan_year_to_date_spend` (
            `id` bigint PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `policy_id` varchar(50) NOT NULL,
            `year` int NOT NULL,
            `organization_id` int NOT NULL,
            `plan_type` enum('INDIVIDUAL', 'FAMILY') default 'INDIVIDUAL',
            `rx_ind_ytd_deductible` int default 0,
            `rx_ind_fam_deductible` int default 0,
            `rx_fam_ytd_oop` int default 0,
            `rx_ind_ytd_oop` int default 0,
            KEY (policy_id),
            FOREIGN KEY (organization_id) REFERENCES organization(`id`)
        );        
        """
    )
