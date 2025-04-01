"""employer_health_plan_deprecated_columns_nullable

Revision ID: 60b3cad6167b
Revises: b0c16254f55c
Create Date: 2024-10-22 16:10:31.522595+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "60b3cad6167b"
down_revision = "3f20054b32c6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        MODIFY COLUMN   `is_deductible_embedded` tinyint(1) DEFAULT NULL,
        MODIFY COLUMN   `is_oop_embedded` tinyint(1) DEFAULT NULL,
        MODIFY COLUMN   `is_second_tier_deductible_embedded` tinyint(1) DEFAULT NULL,
        MODIFY COLUMN   `is_second_tier_oop_embedded` tinyint(1) DEFAULT NULL,
        MODIFY COLUMN   `rx_integrated` tinyint(1) DEFAULT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        MODIFY COLUMN   `is_deductible_embedded` tinyint(1) NOT NULL DEFAULT '0',
        MODIFY COLUMN   `is_oop_embedded` tinyint(1) NOT NULL DEFAULT '0',
        MODIFY COLUMN   `is_second_tier_deductible_embedded` tinyint(1) NOT NULL DEFAULT '0',
        MODIFY COLUMN   `is_second_tier_oop_embedded` tinyint(1) NOT NULL DEFAULT '0',
        MODIFY COLUMN   `rx_integrated` tinyint(1) NOT NULL DEFAULT '1',
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
