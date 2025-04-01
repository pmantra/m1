"""add_localization_field_to_specialty

Revision ID: bac04d40a715
Revises: 0f8a0f07c8f8
Create Date: 2024-09-13 04:24:42.284944+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "bac04d40a715"
down_revision = "0f8a0f07c8f8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE specialty ADD COLUMN searchable_localized_data TEXT;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE specialty DROP COLUMN searchable_localized_data;
        """
    )
