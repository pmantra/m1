"""update_currency_exchange_column_precision

Revision ID: fc38a0c8003d
Revises: e5bca3bff1fc
Create Date: 2024-03-25 13:29:14.829424+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "fc38a0c8003d"
down_revision = "ccc7199f47dd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_request_exchange_rates
        MODIFY COLUMN exchange_rate decimal(12,6) NOT NULL,
        ALGORITHM=COPY,
        LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.reimbursement_request_exchange_rates
        MODIFY COLUMN exchange_rate decimal(8,2) NOT NULL,
        ALGORITHM=COPY,
        LOCK=SHARED;
        """
    )
