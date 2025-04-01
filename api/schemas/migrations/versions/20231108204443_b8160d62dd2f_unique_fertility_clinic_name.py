"""unique_fertility_clinic_name

Revision ID: b8160d62dd2f
Revises: 08718d6ec78b
Create Date: 2023-11-08 20:44:43.637962+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b8160d62dd2f"
down_revision = "08718d6ec78b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `fertility_clinic`
        ADD UNIQUE `uq_fertility_clinic_name` (`name`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `fertility_clinic`
        DROP INDEX `uq_fertility_clinic_name`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
