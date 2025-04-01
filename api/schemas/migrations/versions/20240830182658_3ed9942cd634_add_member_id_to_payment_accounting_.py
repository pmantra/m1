"""add_member_id_to_payment_accounting_entry

Revision ID: 3ed9942cd634
Revises: 4b9f72e66092
Create Date: 2024-08-30 18:26:58.775354+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3ed9942cd634"
down_revision = "d920b3bb6151"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE payment_accounting_entry
        ADD COLUMN member_id int(11) default NULL
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE payment_accounting_entry
        DROP COLUMN member_id
        """
    )
