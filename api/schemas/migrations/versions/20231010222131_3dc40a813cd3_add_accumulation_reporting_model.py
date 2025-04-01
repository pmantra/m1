"""add accumulation reporting model

Revision ID: 3dc40a813cd3
Revises: 0c006e9f0ba9
Create Date: 2023-10-10 22:21:31.789458+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3dc40a813cd3"
down_revision = "af43df6b8718"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `payer_accumulation_reports` (
          `id` bigint(20) NOT NULL AUTO_INCREMENT,
          `payer` enum('UHC', 'CIGNA', 'ESI', 'OHIO_HEALTH'),
          `filename` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `report_date` date DEFAULT NULL,
          `status` enum('NEW', 'SUBMITTED', 'FAILURE'),
          `created_at` datetime DEFAULT NULL,
          `modified_at` datetime DEFAULT NULL,
          PRIMARY KEY (`id`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `payer_accumulation_reports`;
        """
    )
