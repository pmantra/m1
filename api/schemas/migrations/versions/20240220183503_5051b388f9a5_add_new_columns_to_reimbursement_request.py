"""add_new_columns_to_reimbursement_request

Revision ID: 5051b388f9a5
Revises: 2527df8369b5
Create Date: 2024-02-20 18:35:03.084987+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5051b388f9a5"
down_revision = "c0236be4bdac"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_request
        ADD COLUMN transaction_amount int(11) DEFAULT NULL,
        ADD COLUMN usd_amount int(11) DEFAULT NULL,
        ADD COLUMN transaction_currency_code char(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN benefit_currency_code char(3) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN transaction_to_benefit_rate decimal(12,6) DEFAULT NULL,
        ADD COLUMN transaction_to_usd_rate decimal(12,6) DEFAULT NULL,   
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_request
        DROP COLUMN transaction_amount,
        DROP COLUMN usd_amount,
        DROP COLUMN transaction_currency_code,
        DROP COLUMN benefit_currency_code,
        DROP COLUMN transaction_to_benefit_rate,
        DROP COLUMN transaction_to_usd_rate,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )
