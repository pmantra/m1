"""add_unlimited_to_costbreakdown

Revision ID: f455a9a022c3
Revises: 29d361670908
Create Date: 2025-03-18 14:51:56.038935+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "f455a9a022c3"
down_revision = "29d361670908"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.cost_breakdown
        ADD COLUMN is_unlimited BOOLEAN NOT NULL DEFAULT FALSE,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.cost_breakdown
        DROP COLUMN is_unlimited,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
