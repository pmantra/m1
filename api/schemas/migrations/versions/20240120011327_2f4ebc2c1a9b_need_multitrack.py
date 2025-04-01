"""need_multitrack

Revision ID: 2f4ebc2c1a9b
Revises: 7a3765b91219
Create Date: 2024-01-20 01:13:27.767569+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2f4ebc2c1a9b"
down_revision = "7a3765b91219"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `need`
        ADD COLUMN `hide_from_multitrack` bool DEFAULT FALSE,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `need`
        DROP COLUMN `hide_from_multitrack`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)
