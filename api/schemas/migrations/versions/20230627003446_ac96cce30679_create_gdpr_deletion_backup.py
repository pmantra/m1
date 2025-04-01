"""create_gdpr_deletion_backup

Revision ID: ac96cce30679
Revises: 2be0a9ca9ce0
Create Date: 2023-06-27 00:34:46.738344+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ac96cce30679"
down_revision = "d117fca7c2a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gdpr_deletion_backup",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("data", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade():
    op.drop_table("gdpr_deletion_backup")
