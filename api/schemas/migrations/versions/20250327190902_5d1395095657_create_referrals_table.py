"""create referrals table

Revision ID: 5d1395095657
Revises: 25f83c4714fe
Create Date: 2025-03-27 19:09:02.826568+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5d1395095657"
down_revision = "25f83c4714fe"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `referral` (
            `id` bigint(20) AUTO_INCREMENT,
            `user_id` int(11) NOT NULL,
            `referral_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
            `source` varchar(190) COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            CONSTRAINT `user_id_source_uk` UNIQUE (`user_id`, `source`),
            CONSTRAINT `referral_id_uk` UNIQUE (`referral_id`),
            CONSTRAINT `referral_user_fk` FOREIGN KEY (`user_id`) REFERENCES user (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `referral`;
        """
    )
