"""add-oop-col-to-cost-breakdown-table

Revision ID: 03dccbe4f3a2
Revises: b164f0c1cbaa
Create Date: 2023-10-09 13:41:56.427666+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "03dccbe4f3a2"
down_revision = "b164f0c1cbaa"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        ADD COLUMN `oop_applied` int(11) DEFAULT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        DROP COLUMN `oop_applied`;
        """
    )
