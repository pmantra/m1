"""generic_payer_list_table

Revision ID: 7636520812ef
Revises: 7f17df933dc3
Create Date: 2023-11-03 18:57:51.982009+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7636520812ef"
down_revision = "7f17df933dc3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `payer_list` (
            `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `payer_name` enum('UHC', 'Cigna', 'ESI', 'OHIO_HEALTH') NOT NULL,
            `payer_code` VARCHAR(255) DEFAULT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `payer_list`;
        """
    )
