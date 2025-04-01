"""treatment-procedure-cost-credit

Revision ID: c2c8336aa03b
Revises: dc68bccb9001
Create Date: 2023-10-24 14:48:48.609131+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c2c8336aa03b"
down_revision = "0f2481e2ce97"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `treatment_procedure`
        ADD COLUMN `cost_credit` int(11) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `treatment_procedure`
        DROP COLUMN `cost_credit`
        """
    )
