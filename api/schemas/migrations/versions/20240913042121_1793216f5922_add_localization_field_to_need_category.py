"""add_localization_field_to_need_category

Revision ID: 1793216f5922
Revises: 5856f4940eb0
Create Date: 2024-09-13 04:21:21.057498+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1793216f5922"
down_revision = "5856f4940eb0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE need_category ADD COLUMN searchable_localized_data TEXT;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE need_category DROP COLUMN searchable_localized_data;
        """
    )
