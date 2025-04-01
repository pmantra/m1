"""Adds email to the member_profile table

Revision ID: c0cadddbdb44
Revises: 77d9ef7f6f41
Create Date: 2023-02-02 14:19:47.053441+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c0cadddbdb44"
down_revision = "77d9ef7f6f41"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_profile`
        ADD COLUMN `email` VARCHAR(120) DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_profile`
        DROP COLUMN `email`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
