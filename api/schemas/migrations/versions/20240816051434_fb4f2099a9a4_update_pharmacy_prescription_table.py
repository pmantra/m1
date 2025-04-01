"""update_pharmacy_prescription_table

Revision ID: fb4f2099a9a4
Revises: e3d21bc4ec4f
Create Date: 2024-08-16 05:14:34.177643+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "fb4f2099a9a4"
down_revision = "e3d21bc4ec4f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        MODIFY COLUMN `status` enum('SCHEDULED', 'SHIPPED', 'CANCELLED', 'PAID')
        COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'SCHEDULED',
        MODIFY COLUMN `treatment_procedure_id` bigint(20) NULL,
        MODIFY COLUMN `user_id` int(11) NULL,
        MODIFY COLUMN `maven_benefit_id` VARCHAR(16) NULL,
        ADD COLUMN `reimbursement_json` TEXT NULL,
        ADD COLUMN `reimbursement_request_id` bigint(20) NULL,
        ADD COLUMN `user_benefit_id` VARCHAR(16) NULL,
        ADD COLUMN `rx_filled_date` DATETIME NULL,
        DROP INDEX `ix_rx_unique_id`,
        ADD UNIQUE INDEX `ix_unique_rx_unique_id` (`rx_unique_id`),
        ADD INDEX `ix_reimbursement_request_id` (`reimbursement_request_id`),
        ADD CONSTRAINT `reimbursement_request_fk_1` FOREIGN KEY (`reimbursement_request_id`) REFERENCES `reimbursement_request` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
        """
    )


def downgrade():
    # Drop foreign key constraints
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        DROP FOREIGN KEY `treatment_procedure_fk_1`,
        DROP FOREIGN KEY `user_fk_1`,
        DROP FOREIGN KEY `reimbursement_request_fk_1`;
        """
    )

    # Remove indexes
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        DROP INDEX `ix_unique_rx_unique_id`,
        DROP INDEX `ix_reimbursement_request_id`;
        """
    )
    # Modify columns back to their original state
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        MODIFY COLUMN `status` enum('SCHEDULED', 'SHIPPED', 'CANCELLED')
        COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'SCHEDULED',
        MODIFY COLUMN `treatment_procedure_id` bigint(20) NOT NULL,
        MODIFY COLUMN `user_id` int(11) NOT NULL,
        MODIFY COLUMN `maven_benefit_id` VARCHAR(16) NOT NULL;
        """
    )
    # Drop added columns
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        DROP COLUMN `reimbursement_json`,
        DROP COLUMN `reimbursement_request_id`,
        DROP COLUMN `user_benefit_id`,
        DROP COLUMN `rx_filled_date`;
        """
    )
    # Recreate the original non-unique index on rx_unique_id
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        ADD INDEX `ix_rx_unique_id` (`rx_unique_id`);
        """
    )
    # Recreate foreign key constraints
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        ADD CONSTRAINT `treatment_procedure_fk_1` FOREIGN KEY (`treatment_procedure_id`) REFERENCES `treatment_procedure` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        ADD CONSTRAINT `user_fk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
        """
    )
