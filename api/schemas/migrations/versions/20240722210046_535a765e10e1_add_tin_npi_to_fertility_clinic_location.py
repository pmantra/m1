"""add_tin_npi_to_fertility_clinic_location

Revision ID: 535a765e10e1
Revises: 0e92a5770cf7
Create Date: 2024-07-22 21:00:46.005487+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "535a765e10e1"
down_revision = "0e92a5770cf7"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `fertility_clinic_location`
            ADD COLUMN tin VARCHAR(11) COLLATE utf8mb4_unicode_ci NULL UNIQUE,
            ADD COLUMN npi VARCHAR(10) COLLATE utf8mb4_unicode_ci NULL UNIQUE;
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE fertility_clinic_location
            DROP COLUMN tin,
            DROP COLUMN npi;
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    op.execute(sql)
