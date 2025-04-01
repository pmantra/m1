"""Remove metadata fields from organization_employee

Revision ID: 99ca62d89a72
Revises: d44771539a4f
Create Date: 2021-01-25 18:36:30.262368

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "99ca62d89a72"
down_revision = "d44771539a4f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("organization_employee", "metadata_one")
    op.drop_column("organization_employee", "metadata_two")


def downgrade():
    op.add_column(
        "organization_employee", sa.Column("metadata_one", sa.String(80), nullable=True)
    )
    op.add_column(
        "organization_employee", sa.Column("metadata_two", sa.String(80), nullable=True)
    )
