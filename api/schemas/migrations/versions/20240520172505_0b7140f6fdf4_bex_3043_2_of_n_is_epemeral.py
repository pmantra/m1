"""BEX-3043_2_of_n_is_epemeral

Revision ID: 0b7140f6fdf4
Revises: 2f3c5c2b6a97
Create Date: 2024-05-20 17:25:05.196469+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0b7140f6fdf4"
down_revision = "2f3c5c2b6a97"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        alter table bill        
        add is_ephemeral tinyint(1) default 0 
        comment 'Ephemeral bills are used when to display amounts that will never lead to actual money movement ',
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        DROP COLUMN is_ephemeral,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
