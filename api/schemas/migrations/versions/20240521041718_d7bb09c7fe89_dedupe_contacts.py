"""dedupe_contacts

Revision ID: d7bb09c7fe89
Revises: 0b7140f6fdf4
Create Date: 2024-05-21 04:17:18.739641+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d7bb09c7fe89"
down_revision = "0b7140f6fdf4"
branch_labels = None
depends_on = None


def upgrade():
    statement = """
        DELETE FROM fertility_clinic_location_contact WHERE id NOT IN (
            SELECT keep_id FROM (
                (
                    SELECT MIN(id) as keep_id, uuid, fertility_clinic_location_id, name, email
                    FROM fertility_clinic_location_contact
                    GROUP BY uuid, fertility_clinic_location_id, name, email
                ) AS T1
            )
        );
        CREATE UNIQUE INDEX fertility_clinic_location_contact_idx ON fertility_clinic_location_contact(uuid, fertility_clinic_location_id, name, email);
    """
    op.execute(statement)


def downgrade():
    statement = """
        DROP INDEX fertility_clinic_location_contact_idx ON fertility_clinic_location_contact;
    """
    op.execute(statement)
