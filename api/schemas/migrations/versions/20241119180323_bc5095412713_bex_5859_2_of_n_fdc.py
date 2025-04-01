"""BEX-5859_2_of_n_fdc

Revision ID: bc5095412713
Revises: 783572b4dd55
Create Date: 2024-11-19 18:03:23.371074+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "bc5095412713"
down_revision = "783572b4dd55"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
                ALTER TABLE reimbursement_organization_settings
                ADD COLUMN first_dollar_coverage TINYINT(1) UNSIGNED NOT NULL DEFAULT 0,
                ALGORITHM=INPLACE, LOCK=NONE;
            """
    op.execute(sql)


def downgrade():
    sql = """
                ALTER TABLE reimbursement_organization_settings
                DROP COLUMN first_dollar_coverage,
                ALGORITHM=INPLACE, LOCK=NONE;
            """
    op.execute(sql)
