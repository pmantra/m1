"""BEX-5187_5_of_n_update_status

Revision ID: 783572b4dd55
Revises: 2cf995a0d739
Create Date: 2024-11-19 14:25:41.855222+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "783572b4dd55"
down_revision = "2cf995a0d739"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response`
        MODIFY COLUMN `sync_status` enum ('ALEGEUS_SUCCESS', 'ALEGEUS_FAILURE', 'ALEGEUS_PRE_EXISTING_ACCOUNT', 'ALEGEUS_MISSING_ACCOUNT', 'MISSING_WALLET_ERROR', 'MULTIPLE_WALLETS_ERROR', 'UNKNOWN_ERROR', 'PLAN_ERROR', 'EMPLOYER_PLAN_MISSING_ERROR', 'MEMBER_HEALTH_PLAN_OVERLAP_ERROR', 'MEMBER_HEALTH_PLAN_GENERIC_ERROR', 'MEMBER_HEALTH_PLAN_INVALID_DATES_ERROR', 'MANUAL_PROCESSING', 'ALEGEUS_SYNCH_INITIATED', 'WAITING_ON_OPS_ACTION') COLLATE utf8mb4_unicode_ci DEFAULT NULL, 
        ALGORITHM=COPY ,
        LOCK=SHARED
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `annual_insurance_questionnaire_response`
        MODIFY COLUMN `sync_status` enum('ALEGEUS_SUCCESS','ALEGEUS_FAILURE','ALEGEUS_PRE_EXISTING_ACCOUNT','ALEGEUS_MISSING_ACCOUNT','MISSING_WALLET_ERROR','MULTIPLE_WALLETS_ERROR','UNKNOWN_ERROR','PLAN_ERROR') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=COPY,
        LOCK=SHARED
        """
    )
