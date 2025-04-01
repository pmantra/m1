"""add_authz_role_permission_table

Revision ID: 482fe545bd0a
Revises: 1b45db3aebe9
Create Date: 2023-04-22 22:03:19.554925+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "482fe545bd0a"
down_revision = "1b45db3aebe9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_role_permission",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
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
    op.drop_table("authz_role_permission")
