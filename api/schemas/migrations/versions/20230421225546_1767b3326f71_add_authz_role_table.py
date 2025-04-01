"""add_authz_role_table

Revision ID: 1767b3326f71
Revises: 71e8c9a36b8e
Create Date: 2023-04-21 22:55:46.808379+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1767b3326f71"
down_revision = "66ac6f176a5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_role",
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

    op.create_index("idx_authz_role_name", "authz_role", ["name"])


def downgrade():
    op.drop_index("idx_authz_role_name", table_name="authz_role")
    op.drop_table("authz_role")
