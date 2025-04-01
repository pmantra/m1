"""add deductible remaining to cost breakdown

Revision ID: d4fdda56f76f
Revises: 3c1428934dbe
Create Date: 2023-08-28 21:56:13.336417+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d4fdda56f76f"
down_revision = "3c1428934dbe"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        ADD COLUMN `deductible_remaining` int(11) DEFAULT NULL AFTER `overage_amount`;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        DROP COLUMN `deductible_remaining`;
        """
    )
