"""add gift_card_allowed and welcome_box_allowed to org table

Revision ID: 38b8b65722c6
Revises: ab245c928fd6
Create Date: 2023-08-30 20:18:46.828039+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "38b8b65722c6"
down_revision = "ab245c928fd6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        ADD COLUMN `gift_box_allowed` bool DEFAULT NULL,
        ADD COLUMN `welcome_box_allowed` bool NOT NULL DEFAULT FALSE,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `organization`
        DROP COLUMN `gift_box_allowed`,
        DROP COLUMN `welcome_box_allowed`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
