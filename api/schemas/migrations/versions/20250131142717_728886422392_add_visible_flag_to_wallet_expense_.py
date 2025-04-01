"""Add visible flag to Wallet Expense Subtype

Revision ID: 728886422392
Revises: b7540af22b1e
Create Date: 2025-01-31 14:27:17.125173+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "728886422392"
down_revision = "b7540af22b1e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE wallet_expense_subtype
        ADD COLUMN visible tinyint(1) NOT NULL DEFAULT true,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE wallet_expense_subtype
        DROP COLUMN visible,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    )
