"""add_region_to_vertical

Revision ID: 5d2a426b53e1
Revises: 5be3550ee05a
Create Date: 2024-12-23 16:54:53.355515+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5d2a426b53e1"
down_revision = "c44cf0c47f06"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE vertical ADD COLUMN region TEXT, ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE vertical DROP COLUMN region, ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
