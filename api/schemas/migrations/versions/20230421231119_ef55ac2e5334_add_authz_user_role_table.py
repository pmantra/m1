"""add_authz_user_role_table

Revision ID: ef55ac2e5334
Revises: 1767b3326f71
Create Date: 2023-04-21 23:11:19.964228+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ef55ac2e5334"
down_revision = "1767b3326f71"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_user_role",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
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
    op.drop_table("authz_user_role")
