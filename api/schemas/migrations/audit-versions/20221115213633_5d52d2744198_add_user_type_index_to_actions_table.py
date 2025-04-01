"""add user type index to actions table

Revision ID: 5d52d2744198
Revises: ac0313686a1f
Create Date: 2022-11-15 21:36:33.371002+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "5d52d2744198"
down_revision = "ac0313686a1f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE INDEX action_type_user_id ON action (type, user_id);")


def downgrade():
    op.execute("DROP INDEX action_type_user_id ON action;")
