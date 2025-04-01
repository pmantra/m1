"""create-email-domain-denylist

Revision ID: 3fed0805b34e
Revises: b663614483be
Create Date: 2023-06-21 17:38:14.814430+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "3fed0805b34e"
down_revision = "b663614483be"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_domain_denylist",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("domain", sa.VARCHAR(180), nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "modified_at",
            sa.TIMESTAMP,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
    )

    op.create_unique_constraint("uq_domain", "email_domain_denylist", ["domain"])


def downgrade():
    op.drop_table("email_domain_denylist")
