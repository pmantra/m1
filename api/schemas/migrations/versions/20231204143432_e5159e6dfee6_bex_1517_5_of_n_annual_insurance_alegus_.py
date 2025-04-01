"""BEX-1517_5_of_n_annual_insurance_alegus_synch

Revision ID: e5159e6dfee6
Revises: b9e85cc68b7d
Create Date: 2023-12-04 14:34:32.540294+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e5159e6dfee6"
down_revision = "b9e85cc68b7d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response`
        ADD COLUMN `sync_status` enum('ALEGUS_SUCCESS', 'ALEGUS_FAILURE', 'ALEGUS_PRE_EXISTING_ACCOUNT', 'ALEGUS_MISSING_ACCOUNT', 'MISSING_WALLET_ERROR', 'MULTIPLE_WALLETS_ERROR', 'UNKNOWN_ERROR') COLLATE utf8mb4_unicode_ci DEFAULT NULL, 
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response` CHANGE `alegus_synch_datetime` `sync_attempt_at` datetime DEFAULT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response`
        DROP COLUMN `sync_status`,        
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response` CHANGE `sync_attempt_at` `alegus_synch_datetime` datetime DEFAULT NULL;
        """
    )
