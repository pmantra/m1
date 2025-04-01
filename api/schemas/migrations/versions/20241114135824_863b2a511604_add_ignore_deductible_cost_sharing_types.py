"""add_ignore_deductible_cost_sharing_types

Revision ID: 863b2a511604
Revises: 4c4556d86998
Create Date: 2024-11-14 13:58:24.617512+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "863b2a511604"
down_revision = "4c4556d86998"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        MODIFY COLUMN `cost_sharing_type` ENUM('COPAY','COINSURANCE','COPAY_NO_DEDUCTIBLE', 'COINSURANCE_NO_DEDUCTIBLE','COINSURANCE_MIN','COINSURANCE_MAX') NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan_cost_sharing`
        MODIFY COLUMN `cost_sharing_type` ENUM('COPAY','COINSURANCE', 'COINSURANCE_MIN','COINSURANCE_MAX') NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
