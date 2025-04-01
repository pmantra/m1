"""health_profile date_of_birth

Revision ID: f2b1dbb00734
Revises: c383c0f3c9ae
Create Date: 2024-01-27 01:39:41.956534+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f2b1dbb00734"
down_revision = "c383c0f3c9ae"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE health_profile
        ADD COLUMN date_of_birth date DEFAULT NULL,
        ADD INDEX `date_of_birth_idx` (date_of_birth), 
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE health_profile
        DROP COLUMN date_of_birth,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    op.execute(sql)
