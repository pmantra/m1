"""add modified at to cost breakdown table

Revision ID: f4eeddf3cd43
Revises: d67672684340
Create Date: 2023-08-18 14:25:55.415667+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f4eeddf3cd43"
down_revision = "d67672684340"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM `cost_breakdown`;
        ALTER TABLE `cost_breakdown`
        ADD COLUMN `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `cost_breakdown`
        DROP COLUMN `modified_at`;
        """
    )
