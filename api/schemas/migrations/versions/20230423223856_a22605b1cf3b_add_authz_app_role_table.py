"""add_authz_app_role_table

Revision ID: a22605b1cf3b
Revises: f1edb40fc259
Create Date: 2023-04-23 22:38:56.227626+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a22605b1cf3b"
down_revision = "f1edb40fc259"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_app_role",
        sa.Column("app_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("app_id", "role_id"),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "modified_at",
            sa.TIMESTAMP,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("authz_app_role")
