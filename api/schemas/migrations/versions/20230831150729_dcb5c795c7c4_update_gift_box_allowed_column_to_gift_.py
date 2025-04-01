"""update gift_box_allowed column to gift_card_allowed

Revision ID: dcb5c795c7c4
Revises: 38b8b65722c6
Create Date: 2023-08-31 15:07:29.553332+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "dcb5c795c7c4"
down_revision = "38b8b65722c6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        DROP COLUMN `gift_box_allowed`,
        ADD COLUMN `gift_card_allowed` bool DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        DROP COLUMN `gift_card_allowed`,
        ADD COLUMN `gift_box_allowed` bool DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
