"""add created_at and modified_at to user auth

Revision ID: 3e5a8a193791
Revises: 535a765e10e1
Create Date: 2024-07-25 18:08:11.862226+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3e5a8a193791"
down_revision = "535a765e10e1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
            ALTER TABLE user_auth
            ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
            ADD COLUMN modified_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
            ALTER TABLE user_auth
            DROP COLUMN created_at, 
            DROP COLUMN modified_at,
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
