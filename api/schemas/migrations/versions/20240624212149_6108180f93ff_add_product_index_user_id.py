"""Update product to add index for user_id field

Revision ID: 6108180f93ff
Revises: 30920966ae58
Create Date: 2024-06-24 21:21:49.985638+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "6108180f93ff"
down_revision = "c1a624b098f7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `product`
        ADD INDEX `ix_product_user_id` (user_id),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `product`
        DROP INDEX `ix_product_user_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
