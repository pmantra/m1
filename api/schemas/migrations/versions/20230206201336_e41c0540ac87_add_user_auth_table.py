"""add_user_auth_table

Revision ID: e41c0540ac87
Revises: 2d81c91f9160
Create Date: 2023-02-06 20:13:36.079751+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e41c0540ac87"
down_revision = "2d81c91f9160"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_auth",
        sa.Column("id", sa.Integer, nullable=False, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("user.id", ondelete="cascade"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("external_id", sa.String(120), unique=True, index=True),
        sa.Column("refresh_token", sa.String(120)),
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `user_auth`;")
