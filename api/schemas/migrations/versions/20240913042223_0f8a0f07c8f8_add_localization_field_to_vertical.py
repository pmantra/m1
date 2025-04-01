"""add_localization_field_to_vertical

Revision ID: 0f8a0f07c8f8
Revises: 1793216f5922
Create Date: 2024-09-13 04:22:23.560369+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0f8a0f07c8f8"
down_revision = "1793216f5922"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE vertical ADD COLUMN searchable_localized_data TEXT;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE vertical DROP COLUMN searchable_localized_data;
        """
    )
