"""add_calc_config_column_to_cost_breakdown

Revision ID: 2ae48a561d61
Revises: ec10a90340d3
Create Date: 2024-02-12 17:15:48.476297+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2ae48a561d61"
down_revision = "f546b47c30b7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE cost_breakdown
        ADD COLUMN calc_config text COLLATE utf8mb4_unicode_ci DEFAULT NULL after `cost_breakdown_type`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE cost_breakdown 
        DROP COLUMN calc_config,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
