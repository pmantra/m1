"""BEX-5749-wallet-e9y-black-list

Revision ID: 4c4556d86998
Revises: 177bd932f17d
Create Date: 2024-11-13 15:27:11.221639+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "4c4556d86998"
down_revision = "177bd932f17d"
branch_labels = None
depends_on = None


def upgrade():
    create_table_sql = """
    CREATE TABLE `reimbursement_wallet_eligibility_blacklist` (
        `id` bigint(20) NOT NULL AUTO_INCREMENT,
        `reimbursement_wallet_id` bigint(20) NOT NULL,
        `reason` varchar(1024) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `creator_id` int(11) NOT NULL,
        `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
        `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        `deleted_at` datetime DEFAULT NULL,
        PRIMARY KEY (`id`),
        KEY `reimbursement_wallet_eligibility_blacklist_ibfk_1` (`reimbursement_wallet_id`),
        KEY `reimbursement_wallet_eligibility_blacklist_ibfk_2` (`creator_id`),
        CONSTRAINT `reimbursement_wallet_eligibility_blacklist_ibfk_1` 
            FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
        CONSTRAINT `reimbursement_wallet_eligibility_blacklist_ibfk_2` 
            FOREIGN KEY (`creator_id`) REFERENCES `user` (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    op.execute(create_table_sql)


def downgrade():
    drop_table_sql = """
    DROP TABLE IF EXISTS `reimbursement_wallet_eligibility_blacklist`;
    """

    op.execute(drop_table_sql)
