"""add_order_id_to_pharmacy_prescription

Revision ID: fb507e9b4700
Revises: be2c66146bab
Create Date: 2023-11-10 15:51:55.840524+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "fb507e9b4700"
down_revision = "be2c66146bab"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        ADD COLUMN `rx_order_id` VARCHAR(255) NOT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `pharmacy_prescription`
        DROP COLUMN `rx_order_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
