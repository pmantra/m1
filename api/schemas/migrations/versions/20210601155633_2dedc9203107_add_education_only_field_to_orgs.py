"""Add education_only field to orgs

Revision ID: 2dedc9203107
Revises: 3ad95c89fad8
Create Date: 2021-06-01 15:56:33.908818+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2dedc9203107"
down_revision = "3ad95c89fad8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization",
        sa.Column("education_only", sa.Boolean, default=False, nullable=False),
    )


def downgrade():
    op.drop_column("organization", "education_only")
