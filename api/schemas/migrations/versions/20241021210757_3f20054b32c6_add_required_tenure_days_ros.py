"""add_required_tenure_days_ros

Revision ID: 3f20054b32c6
Revises: c49eb1d482bc
Create Date: 2024-10-21 21:07:57.063881+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3f20054b32c6"
down_revision = "c49eb1d482bc"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
                ALTER TABLE reimbursement_organization_settings
                ADD COLUMN required_tenure_days SMALLINT(6) UNSIGNED NOT NULL DEFAULT 0,
                ALGORITHM=COPY, LOCK=SHARED;
            """
    op.execute(sql)


def downgrade():
    sql = """
                ALTER TABLE reimbursement_organization_settings
                DROP COLUMN required_tenure_days,
                ALGORITHM=COPY, LOCK=SHARED;
            """
    op.execute(sql)
