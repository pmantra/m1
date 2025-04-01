"""employer_health_plan_add_rx_integration_enum

Revision ID: f0212045d8e7
Revises: 324a95a1a30f
Create Date: 2024-10-23 17:54:02.256751+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f0212045d8e7"
down_revision = "324a95a1a30f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN   `rx_integration` enum('NONE','FULL','ACCUMULATION') COLLATE utf8mb4_unicode_ci DEFAULT 'FULL',
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN   `rx_integration`,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
