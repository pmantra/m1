""" Adds email to the practitioner_profile table

Revision ID: 9bffb48b5cbb
Revises: 8e05adaeed11
Create Date: 2023-01-30 14:23:34.829298+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "9bffb48b5cbb"
down_revision = "8e05adaeed11"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `practitioner_profile`
        ADD COLUMN `email` VARCHAR(120) DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `practitioner_profile`
        DROP COLUMN `email`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
