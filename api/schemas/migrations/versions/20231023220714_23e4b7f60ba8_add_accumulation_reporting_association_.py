"""add accumulation reporting association tables

Revision ID: 23e4b7f60ba8
Revises: 96c4b2926832
Create Date: 2023-10-23 22:07:14.166276+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "23e4b7f60ba8"
down_revision = "96c4b2926832"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `accumulation_treatment_mapping` (
          `id` bigint(20) NOT NULL AUTO_INCREMENT,
          `accumulation_uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
          `treatment_procedure_uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
          `treatment_accumulation_status` enum('WAITING', 'PAID', 'ROW_ERROR', 'PROCESSED', 'SUBMITTED'),
          `report_id` bigint(20) NOT NULL,
          `completed_at` datetime DEFAULT NULL,
          `created_at` datetime DEFAULT NULL,
          `modified_at` datetime DEFAULT NULL,
          PRIMARY KEY (`id`),
          CONSTRAINT `payer_accumulation_reports_fk_1` FOREIGN KEY (`report_id`) REFERENCES `payer_accumulation_reports` (`id`) ON DELETE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `accumulation_treatment_mapping`;
        """
    )
