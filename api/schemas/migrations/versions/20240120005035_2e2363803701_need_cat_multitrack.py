"""need_cat_multitrack

Revision ID: 2e2363803701
Revises: cafebb1294bb
Create Date: 2024-01-20 00:50:35.946314+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2e2363803701"
down_revision = "cafebb1294bb"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `need_category`
        ADD COLUMN `hide_from_multitrack` bool DEFAULT FALSE,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `need_category`
        DROP COLUMN `hide_from_multitrack`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)
