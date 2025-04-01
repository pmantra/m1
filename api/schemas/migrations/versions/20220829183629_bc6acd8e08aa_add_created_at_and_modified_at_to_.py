"""add created_at and modified_at to Wallet Tables

Revision ID: bc6acd8e08aa
Revises: 1fa8503dc998
Create Date: 2022-08-29 18:36:29.437196+00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "bc6acd8e08aa"
down_revision = "1fa8503dc998"
branch_labels = None
depends_on = None

from wallet.models import (
    reimbursement,
    reimbursement_organization_settings,
    reimbursement_request_source,
    reimbursement_wallet,
    reimbursement_wallet_debit_card,
)


def get_wallet_snowflake_base():
    """Tables where Wallet is using Snowflake base"""
    return [
        reimbursement.ReimbursementRequestCategory,
        reimbursement.ReimbursementRequest,
        reimbursement.ReimbursementPlanCoverageTier,
        reimbursement.ReimbursementPlan,
        reimbursement.ReimbursementWalletPlanHDHP,
        reimbursement.ReimbursementAccountType,
        reimbursement.ReimbursementAccount,
        reimbursement.ReimbursementClaim,
        reimbursement.ReimbursementRequestExchangeRates,
        reimbursement_organization_settings.ReimbursementOrganizationSettings,
        reimbursement_organization_settings.ReimbursementOrgSettingCategoryAssociation,
        reimbursement_request_source.ReimbursementRequestSource,
        reimbursement_wallet.ReimbursementWallet,
        reimbursement_wallet_debit_card.ReimbursementWalletDebitCard,
    ]


def upgrade():
    # Add new created at and modified at to the DB tables
    for base_snowflake_table in get_wallet_snowflake_base():
        with op.batch_alter_table(base_snowflake_table.__tablename__) as batch_op:
            # Will be changed to not nullable after data is backfilled
            batch_op.add_column(sa.Column("created_at", sa.DateTime, nullable=True))
            batch_op.add_column(sa.Column("modified_at", sa.DateTime, nullable=True))


def downgrade():
    for base_snowflake_table in get_wallet_snowflake_base():
        # Drop created_at and modified_at
        with op.batch_alter_table(base_snowflake_table.__tablename__) as batch_op:
            batch_op.drop_column("created_at")
            batch_op.drop_column("modified_at")
