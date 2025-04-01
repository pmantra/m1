"""Add created_at, modified_at, terminated_at to maven.organization

Revision ID: 6457ba93b77d
Revises: e54cfdd38fcb
Create Date: 2023-05-25 20:08:44.000478+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6457ba93b77d"
down_revision = "e54cfdd38fcb"
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

    op.execute(
        """ ALTER TABLE organization
        DROP COLUMN created_at, 
        DROP COLUMN modified_at,
        DROP COLUMN terminated_at,
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )
