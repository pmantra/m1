"""add 'us only' checkbox to orgs

Revision ID: 39147f439620
Revises: bbdad7054e01
Create Date: 2022-06-14 15:00:39.689888+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "39147f439620"
down_revision = "bbdad7054e01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization",
        sa.Column("US_restricted", sa.Boolean, default=False, nullable=False),
    )


def downgrade():
    op.drop_column("organization", "US_restricted")
