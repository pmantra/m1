"""add_idp_metadata_column

Revision ID: 7079b9fa4d38
Revises: 1a2340ec21dd
Create Date: 2022-08-29 18:12:46.089085+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7079b9fa4d38"
down_revision = "1a2340ec21dd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS `identity_provider_repository`;")
    op.create_table(
        "identity_provider",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True, index=True),
        sa.Column("metadata", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "modified_at",
            sa.TIMESTAMP,
            nullable=False,
            # See: https://docs.sqlalchemy.org/en/14/dialects/mysql.html#mysql-timestamp-onupdate
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `identity_provider`;")
