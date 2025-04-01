"""add_benefits_url_to_organization

Revision ID: b4fc98a5fe8f
Revises: 09cb47c25048
Create Date: 2024-10-15 17:24:23.105035+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b4fc98a5fe8f"
down_revision = "09cb47c25048"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        ADD COLUMN `benefits_url` VARCHAR(255) DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        DROP COLUMN `benefits_url`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
