"""add_authz_scope_table

Revision ID: c971d36c5290
Revises: 482fe545bd0a
Create Date: 2023-04-22 22:09:23.961789+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c971d36c5290"
down_revision = "482fe545bd0a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_scope",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.String(256)),
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

    op.create_index("idx_authz_scope_name", "authz_scope", ["name"])


def downgrade():
    op.drop_index("idx_authz_scope_name", table_name="authz_scope")
    op.drop_table("authz_scope")
