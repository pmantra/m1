"""BEX-4824-wallet-sync-meta

Revision ID: 2a4b2550d1f0
Revises: 5b6af8f0f8cb
Create Date: 2024-10-31 17:08:25.957283+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "2a4b2550d1f0"
down_revision = "5b6af8f0f8cb"
branch_labels = None
depends_on = None


def upgrade():
    # Create table SQL
    create_table_sql = """
        CREATE TABLE `reimbursement_wallet_eligibility_sync_meta` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT,
            `wallet_id` bigint(20) NOT NULL,
            `sync_time` datetime NOT NULL,
            `sync_initiator` enum('CRON_JOB', 'MANUAL') COLLATE utf8mb4_unicode_ci NOT NULL,
            `change_type` enum('ROS_CHANGE', 'DISQUALIFIED', 'RUNOUT', 'DEPENDANT_CHANGE') COLLATE utf8mb4_unicode_ci NOT NULL,
            `previous_end_date` datetime DEFAULT NULL,
            `latest_end_date` datetime DEFAULT NULL,
            `previous_ros_id` bigint(20) NOT NULL,
            `latest_ros_id` bigint(20) DEFAULT NULL,
            `user_id` int(11) NOT NULL,
            `dependents_ids` text NOT NULL COMMENT 'Comma-separated list of dependent IDs',
            `is_dry_run` tinyint(1) NOT NULL DEFAULT '0',
            `previous_wallet_state` enum('PENDING', 'QUALIFIED', 'DISQUALIFIED', 'EXPIRED', 'RUNOUT') COLLATE utf8mb4_unicode_ci DEFAULT 'QUALIFIED',
            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `ix_reimbursement_wallet_eligibility_sync_meta_wallet_id` (`wallet_id`),
            KEY `ix_reimbursement_wallet_eligibility_sync_meta_sync_time` (`sync_time`),
            KEY `ix_reimbursement_wallet_eligibility_sync_meta_user_id` (`user_id`),
            CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_wallet_id` FOREIGN KEY (`wallet_id`) REFERENCES `reimbursement_wallet` (`id`),
            CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_previous_ros_id` FOREIGN KEY (`previous_ros_id`) REFERENCES `reimbursement_organization_settings` (`id`),
            CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_latest_ros_id` FOREIGN KEY (`latest_ros_id`) REFERENCES `reimbursement_organization_settings` (`id`),
            CONSTRAINT `fk_reimbursement_wallet_eligibility_sync_meta_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
        );
    """
    op.execute(create_table_sql)


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `reimbursement_wallet_eligibility_sync_meta`;
    """
    )
