"""BEX-4511_org_id

Revision ID: 78957965e950
Revises: 500d12b5386b
Create Date: 2024-09-17 16:45:30.815909+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "78957965e950"
down_revision = "500d12b5386b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE organization_invoicing_settings
        ADD UNIQUE (organization_id);
    """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE organization_invoicing_settings
        DROP INDEX organization_id;
    """
    )
