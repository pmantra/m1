"""add_authz_app_table

Revision ID: f1edb40fc259
Revises: 0b275c18f7e2
Create Date: 2023-04-23 22:37:38.482753+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1edb40fc259"
down_revision = "0b275c18f7e2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authz_app",
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

    op.create_index("idx_authz_app_name", "authz_app", ["name"])


def downgrade():
    op.drop_index("idx_authz_app_name", table_name="authz_app")
    op.drop_table("authz_app")
