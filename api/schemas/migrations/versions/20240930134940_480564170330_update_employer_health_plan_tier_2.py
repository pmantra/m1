"""update_employer_health_plan_tier_2

Revision ID: 480564170330
Revises: 915796353507
Create Date: 2024-09-30 13:49:40.546688+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "480564170330"
down_revision = "915796353507"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `second_tier_ind_deductible` int(11) DEFAULT NULL AFTER rx_fam_oop_max_limit,
        ADD COLUMN `second_tier_ind_oop` int(11) DEFAULT NULL AFTER second_tier_ind_deductible,
        ADD COLUMN `second_tier_family_deductible` int(11) DEFAULT NULL AFTER second_tier_ind_oop,
        ADD COLUMN `second_tier_family_oop` int(11) DEFAULT NULL AFTER second_tier_family_deductible,
        ADD COLUMN `is_second_tier_deductible_embedded` tinyint(1) NOT NULL DEFAULT '0' AFTER second_tier_family_oop,
        ADD COLUMN `is_second_tier_oop_embedded` tinyint(1) NOT NULL DEFAULT '0' AFTER is_second_tier_deductible_embedded;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `second_tier_ind_deductible`,
        DROP COLUMN `second_tier_ind_oop`,
        DROP COLUMN `second_tier_family_deductible`,
        DROP COLUMN `second_tier_family_oop`,
        DROP COLUMN `is_second_tier_deductible_embedded`,
        DROP COLUMN `is_second_tier_oop_embedded`;
        """
    )
