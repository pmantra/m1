"""add_authz_permission_table

Revision ID: 1b45db3aebe9
Revises: ef55ac2e5334
Create Date: 2023-04-22 22:01:02.292174+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1b45db3aebe9"
down_revision = "ef55ac2e5334"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_permission",
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

    op.create_index("idx_authz_permission_name", "authz_permission", ["name"])


def downgrade():
    op.drop_index("idx_authz_permission_name", table_name="authz_permission")
    op.drop_table("authz_permission")
