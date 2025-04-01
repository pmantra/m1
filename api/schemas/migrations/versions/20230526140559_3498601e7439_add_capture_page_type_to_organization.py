"""add_capture_page_type_to_organization

Revision ID: 3498601e7439
Revises: e54cfdd38fcb
Create Date: 2023-05-26 14:05:59.395859+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "3498601e7439"
down_revision = "332226e2314d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE organization
        ADD COLUMN capture_page_type enum('FORM','NO_FORM') DEFAULT 'NO_FORM',
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE organization
        DROP COLUMN capture_page_type,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
