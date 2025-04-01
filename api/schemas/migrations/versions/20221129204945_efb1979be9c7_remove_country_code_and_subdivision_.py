"""remove_country_code_and_subdivision_code_from_user_table

Revision ID: efb1979be9c7
Revises: 6ff2942c2b50
Create Date: 2022-11-29 20:49:45.120634+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "efb1979be9c7"
down_revision = "6ff2942c2b50"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `user` 
        DROP COLUMN `country_code`,
        DROP COLUMN `subdivision_code`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():

    op.execute(
        """
        ALTER TABLE `user` 
        ADD COLUMN `country_code` VARCHAR(2),
        ADD COLUMN `subdivision_code` VARCHAR(6),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
