"""add_payroll_date_to_wallet_client_reports

Revision ID: a2aab8ce095e
Revises: f4eeddf3cd43
Create Date: 2023-08-21 02:46:32.159142+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a2aab8ce095e"
down_revision = "f4eeddf3cd43"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `wallet_client_reports`
        ADD COLUMN `payroll_date` date DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `wallet_client_reports`
        DROP COLUMN `payroll_date`,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
