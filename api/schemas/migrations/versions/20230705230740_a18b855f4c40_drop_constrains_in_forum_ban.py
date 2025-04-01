"""drop-constrains-in-forum-ban

Revision ID: a18b855f4c40
Revises: f2eeec063de9
Create Date: 2023-07-05 23:07:40.069191+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a18b855f4c40"
down_revision = "f2eeec063de9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE forum_ban "
        "DROP FOREIGN KEY forum_ban_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )
    op.execute(
        "ALTER TABLE forum_ban "
        "DROP FOREIGN KEY forum_ban_ibfk_2, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    # forum_ban_ibfk_1
    op.execute("DROP INDEX user_id ON forum_ban")
    op.execute("CREATE INDEX user_id ON forum_ban(user_id);")
    op.execute(
        "ALTER TABLE forum_ban "
        "ADD CONSTRAINT forum_ban_ibfk_1 "
        "FOREIGN KEY (user_id) REFERENCES user(id)"
    )

    # recover forum_ban_ibfk_2
    op.execute("DROP INDEX created_by_user_id ON forum_ban")
    op.execute("CREATE INDEX created_by_user_id ON forum_ban(created_by_user_id);")
    op.execute(
        "ALTER TABLE forum_ban "
        "ADD CONSTRAINT forum_ban_ibfk_2 "
        "FOREIGN KEY (created_by_user_id) REFERENCES user(id)"
    )
