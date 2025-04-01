"""add_date_processing_to_incentive_fulfillment

Revision ID: a41858119368
Revises: 6b607e7b6e42
Create Date: 2024-01-09 18:20:11.024704+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a41858119368"
down_revision = "049cafa2bba1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `incentive_fulfillment`
        ADD COLUMN `date_processing` datetime DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `incentive_fulfillment`
        DROP COLUMN `date_processing`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
