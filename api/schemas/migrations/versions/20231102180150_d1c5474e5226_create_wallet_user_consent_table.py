"""Create wallet user consent table

Revision ID: d1c5474e5226
Revises: dc87b6d02b42
Create Date: 2023-11-02 18:01:50.343625+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d1c5474e5226"
down_revision = "dc87b6d02b42"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `wallet_user_consent` (
        `id` bigint(20) NOT NULL AUTO_INCREMENT,
        `consent_giver_id` int(11) NOT NULL,
        `consent_recipient_id` int(11) DEFAULT NULL,
        `recipient_email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `reimbursement_wallet_id` bigint(20) NOT NULL,
        `operation` enum('GIVE_CONSENT','REVOKE_CONSENT') COLLATE utf8mb4_unicode_ci NOT NULL,
        `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `wallet_user_consent`;
        """
    )
