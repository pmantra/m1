"""add uuid to cost breakdown table

Revision ID: 5c0b8c5900fa
Revises: e6292f8781f4
Create Date: 2023-08-15 19:12:56.268571+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5c0b8c5900fa"
down_revision = "e6292f8781f4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM `cost_breakdown`;
        ALTER TABLE `cost_breakdown`
        ADD COLUMN `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL AFTER `id`;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        DROP COLUMN `uuid`;
        """
    )
