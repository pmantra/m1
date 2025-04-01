"""add_use_custom_rate_to_org_table

Revision ID: e74b7a0584e3
Revises: 8a4eee290d8a
Create Date: 2024-08-13 13:56:03.887348+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e74b7a0584e3"
down_revision = "8a4eee290d8a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        ADD COLUMN `use_custom_rate` BOOLEAN DEFAULT FALSE,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        DROP COLUMN `use_custom_rate`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
