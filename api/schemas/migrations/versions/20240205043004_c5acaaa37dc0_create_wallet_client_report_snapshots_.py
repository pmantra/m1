"""create_wallet_client_report_snapshots_table

Revision ID: c5acaaa37dc0
Revises: 59bc3491147b
Create Date: 2024-02-05 04:30:04.997200+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c5acaaa37dc0"
down_revision = "59bc3491147b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
      CREATE TABLE `wallet_client_report_snapshots` (
          `id` bigint(20) NOT NULL,
          `reimbursement_wallet_id` bigint(20) NOT NULL,
          `wallet_client_report_id` bigint(20) NOT NULL,
          `total_program_to_date_amount` decimal(8,2) DEFAULT NULL,
          PRIMARY KEY (`id`),
          KEY `reimbursement_wallet_id_key` (`reimbursement_wallet_id`),
          KEY `wallet_client_report_id_key` (`wallet_client_report_id`),
          CONSTRAINT `wallet_client_report_snapshots_ibfk_1` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
          CONSTRAINT `wallet_client_report_snapshots_ibfk_2` FOREIGN KEY (`wallet_client_report_id`) REFERENCES `wallet_client_reports` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `wallet_client_report_snapshots`;
        """
    )
