"""create_pharmacy_prescription_table

Revision ID: 40399bb85f5d
Revises: 916c42ba6775
Create Date: 2023-10-18 21:30:43.029068+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "40399bb85f5d"
down_revision = "916c42ba6775"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `pharmacy_prescription`(
        `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
        `treatment_procedure_id` bigint(20) NOT NULL,
        `rx_unique_id` VARCHAR(120) NOT NULL,
        `maven_benefit_id` VARCHAR(16) NOT NULL,
        `status` enum('SCHEDULED', 'SHIPPED', 'CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'SCHEDULED',
        `amount_owed` int(11) NOT NULL,
        `ncpdp_number` VARCHAR(20) NOT NULL,
        `ndc_number` VARCHAR(20) NOT NULL,
        `rx_name` VARCHAR(255) NOT NULL,
        `rx_description` TEXT NOT NULL,
        `rx_first_name` VARCHAR(255) NOT NULL, 
        `rx_last_name` VARCHAR(255) NOT NULL,
        `rx_received_date` DATETIME NOT NULL, 
        `scheduled_ship_date` DATETIME,
        `actual_ship_date` DATETIME,
        `cancelled_date` DATETIME,
        `scheduled_json` TEXT,
        `shipped_json` TEXT,
        `cancelled_json` TEXT,
        `user_id` int(11) NOT NULL,
        `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
        `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX  `ix_rx_unique_id` (`rx_unique_id`),
        INDEX `ix_treatment_procedure_id` (`treatment_procedure_id`),
        CONSTRAINT `treatment_procedure_fk_1` FOREIGN KEY (`treatment_procedure_id`) REFERENCES `treatment_procedure` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `user_fk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `pharmacy_prescription`;
        """
    )
