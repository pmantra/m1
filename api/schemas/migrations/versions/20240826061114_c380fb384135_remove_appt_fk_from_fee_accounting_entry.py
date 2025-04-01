"""remove_appt_fk_from_fee_accounting_entry

Revision ID: c380fb384135
Revises: fb4f2099a9a4
Create Date: 2024-08-26 06:11:14.999635+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c380fb384135"
down_revision = "3ed9942cd634"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE fee_accounting_entry
        DROP FOREIGN KEY fee_accounting_entry_ibfk_1
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE fee_accounting_entry
        ADD CONSTRAINT fee_accounting_entry_ibfk_1 FOREIGN KEY (appointment_id) REFERENCES appointment(id)
        """
    )
