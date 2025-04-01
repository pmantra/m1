"""add_card_funding_to_bill_table

Revision ID: b2d50388f63b
Revises: c0236be4bdac
Create Date: 2024-02-21 15:58:16.962128+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b2d50388f63b"
down_revision = "e2b98f456b6e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE bill 
        ADD COLUMN card_funding ENUM('CREDIT', 'DEBIT', 'PREPAID', 'UNKNOWN') DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE bill DROP COLUMN card_funding,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
