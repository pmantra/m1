"""created-at-user-flags

Revision ID: e6f81ff574bc
Revises: a2e30796ff8a
Create Date: 2023-07-18 09:58:39.226564+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "e6f81ff574bc"
down_revision = "3f437dbaed30"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE user_flag_users ADD COLUMN created_at DATETIME DEFAULT NULL, ALGORITHM=INPLACE,LOCK=NONE;"
    )


def downgrade():
    op.execute("ALTER TABLE user_flag_users DROP COLUMN created_at")
