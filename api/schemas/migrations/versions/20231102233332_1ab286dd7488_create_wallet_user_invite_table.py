"""Create Wallet user invite table

Revision ID: 1ab286dd7488
Revises: d1c5474e5226
Create Date: 2023-11-02 23:33:32.174744+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1ab286dd7488"
down_revision = "d1c5474e5226"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `wallet_user_invite` (
            `id` char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
            `created_by_user_id` int(11) NOT NULL,
            `reimbursement_wallet_id` bigint(20) NOT NULL,
            `date_of_birth_provided` char(10) COLLATE utf8mb4_unicode_ci NOT NULL,
            `email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            `claimed` tinyint(1) NOT NULL,
            `has_info_mismatch` tinyint(1) NOT NULL,
            `email_sent` tinyint(1) NOT NULL,
            `created_at` datetime NOT NULL,
            `modified_at` datetime NOT NULL,
            PRIMARY KEY (`id`),
            KEY `ix_wallet_user_invite_created_at` (`created_at`),
            KEY `ix_wallet_user_invite_created_by_user_id` (`created_by_user_id`),
            KEY `ix_wallet_user_invite_reimbursement_wallet_id` (`reimbursement_wallet_id`),
            KEY `ix_wallet_user_invite_email` (`email`),
            CONSTRAINT `wallet_user_invite_ibfk_1` FOREIGN KEY (`created_by_user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
            CONSTRAINT `wallet_user_invite_ibfk_2` FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `wallet_user_invite`;")
