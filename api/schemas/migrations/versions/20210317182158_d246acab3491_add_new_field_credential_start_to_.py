"""Add new field credential_start to practitioner_profile table

Revision ID: d246acab3491
Revises: 8f5b9f6e4dd3
Create Date: 2021-03-17 18:21:58.890951

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d246acab3491"
down_revision = "8f5b9f6e4dd3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "practitioner_profile",
        sa.Column("credential_start", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_column("practitioner_profile", "credential_start")
