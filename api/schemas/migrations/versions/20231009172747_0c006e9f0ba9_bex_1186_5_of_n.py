"""BEX-1186_5_of_n

Revision ID: 0c006e9f0ba9
Revises: 03dccbe4f3a2
Create Date: 2023-10-09 17:27:47.763742+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0c006e9f0ba9"
down_revision = "03dccbe4f3a2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        ADD COLUMN `payment_method_type` enum('card', 'us_bank_account') COLLATE utf8mb4_unicode_ci DEFAULT NULL,  
        ADD COLUMN `payment_method_id` VARCHAR(30) DEFAULT NULL, 
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        DROP COLUMN `payment_method_type`,
        DROP COLUMN `payment_method_id`,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
