"""add_localization_field_to_need

Revision ID: 5856f4940eb0
Revises: 396d2c123cdc
Create Date: 2024-09-13 04:10:18.621447+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5856f4940eb0"
down_revision = "396d2c123cdc"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE need ADD COLUMN searchable_localized_data TEXT;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE need DROP COLUMN searchable_localized_data;
        """
    )
