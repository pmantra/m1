"""add_is_unlimited_to_category_association

Revision ID: 68439761c5a1
Revises: 634ffa1ce3fc
Create Date: 2025-02-18 21:45:19.065054+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "68439761c5a1"
down_revision = "634ffa1ce3fc"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_organization_settings_allowed_category
        ADD COLUMN is_unlimited BOOLEAN NOT NULL DEFAULT FALSE,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_organization_settings_allowed_category
        DROP COLUMN is_unlimited,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
