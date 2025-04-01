"""update_reimbursement_request_exchange_rates_unique_constraint

Revision ID: 789394635a74
Revises: 1dab28f1a659
Create Date: 2024-08-14 20:18:10.496886+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "789394635a74"
down_revision = "1dab28f1a659"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request_exchange_rates`
        DROP KEY `uq_source_target_rate`,
        ADD UNIQUE KEY `uq_source_target_date_org` (`source_currency`,`target_currency`,`trading_date`, `organization_id`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request_exchange_rates`
        DROP KEY `uq_source_target_date_org`,
        ADD UNIQUE KEY `uq_source_target_rate` (`source_currency`,`target_currency`,`trading_date`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
