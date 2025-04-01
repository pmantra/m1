"""add_alegeus_id_to_reimbursement_wallet

Revision ID: cf925a6b0ada
Revises: ba3bae761b2b
Create Date: 2023-09-14 15:05:17.870495+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "cf925a6b0ada"
down_revision = "ba3bae761b2b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_wallet`
        ADD COLUMN `alegeus_id` VARCHAR(255) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_wallet`
        DROP COLUMN `alegeus_id`,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
