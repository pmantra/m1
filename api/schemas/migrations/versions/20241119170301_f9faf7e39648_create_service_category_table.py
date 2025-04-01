"""Create service category table

Revision ID: f9faf7e39648
Revises: 3e2e9458f281
Create Date: 2024-11-19 17:03:01.117601+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "f9faf7e39648"
down_revision = "3e2e9458f281"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `reimbursement_service_category` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `category` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
            `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `reimbursement_service_category`;
        """
    )
