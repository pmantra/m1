"""add_authz_user_scope_table

Revision ID: 0b275c18f7e2
Revises: c971d36c5290
Create Date: 2023-04-22 22:12:38.205355+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0b275c18f7e2"
down_revision = "c971d36c5290"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_user_scope",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "scope_id"),
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
    op.drop_table("authz_user_scope")
