"""add_backfill_reimbursement_wallet_state_table

Revision ID: 263de358bad4
Revises: e501d62a6d76
Create Date: 2023-09-28 13:48:32.971030+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "263de358bad4"
down_revision = "690f6242b8df"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `backfill_reimbursement_wallet_state` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `reimbursement_wallet_id` bigint(20) NOT NULL,
            `eligibility_member_id` int(11) DEFAULT NULL,
            `eligibility_verification_id` int(11) DEFAULT NULL,
            PRIMARY KEY (`id`),
            KEY `reimbursement_wallet_id` (`reimbursement_wallet_id`),
            KEY `eligibility_member_id` (`eligibility_member_id`),
            KEY `eligibility_verification_id` (`eligibility_verification_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;   
    """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `backfill_reimbursement_wallet_state`
        """
    )
