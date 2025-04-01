"""Add-terminated-created-modified-for-orgtable-with-downgrade

Revision ID: 9ee150d5d5df
Revises: 8479c3c5a8a0
Create Date: 2023-05-31 19:12:06.100204+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9ee150d5d5df"
down_revision = "8479c3c5a8a0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ ALTER TABLE organization
        ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
        ADD COLUMN modified_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        ADD COLUMN terminated_at DATETIME,
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )


def downgrade():
    op.execute(
        """ ALTER TABLE organization
        DROP COLUMN created_at, 
        DROP COLUMN modified_at,
        DROP COLUMN terminated_at,
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )
