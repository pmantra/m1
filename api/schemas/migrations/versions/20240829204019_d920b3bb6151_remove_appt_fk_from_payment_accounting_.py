"""remove_appt_fk_from_payment_accounting_entry

Revision ID: d920b3bb6151
Revises: 4b9f72e66092
Create Date: 2024-08-29 20:40:19.580023+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d920b3bb6151"
down_revision = "4b9f72e66092"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE payment_accounting_entry
        DROP FOREIGN KEY payment_accounting_entry_ibfk_1
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE payment_accounting_entry
        ADD CONSTRAINT payment_accounting_entry_ibfk_1 FOREIGN KEY (appointment_id) REFERENCES appointment(id)
        """
    )
