"""BEX-1517_7.1_of_n_annual_insurance_alegeus_synch

Revision ID: 42bec96e5dc5
Revises: 86e546aa6f6d
Create Date: 2023-12-05 20:19:06.768292+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "42bec96e5dc5"
down_revision = "86e546aa6f6d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response`
        MODIFY COLUMN `sync_status` enum('ALEGEUS_SUCCESS', 'ALEGEUS_FAILURE', 'ALEGEUS_PRE_EXISTING_ACCOUNT', 'ALEGEUS_MISSING_ACCOUNT', 'MISSING_WALLET_ERROR', 'MULTIPLE_WALLETS_ERROR', 'UNKNOWN_ERROR', 'PLAN_ERROR') COLLATE utf8mb4_unicode_ci DEFAULT NULL, 
        ALGORITHM=COPY,
        LOCK=SHARED
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response`
        MODIFY COLUMN `sync_status` enum('ALEGUS_SUCCESS', 'ALEGUS_FAILURE', 'ALEGUS_PRE_EXISTING_ACCOUNT', 'ALEGUS_MISSING_ACCOUNT', 'MISSING_WALLET_ERROR', 'MULTIPLE_WALLETS_ERROR', 'UNKNOWN_ERROR') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=COPY,
        LOCK=SHARED
        """
    )
