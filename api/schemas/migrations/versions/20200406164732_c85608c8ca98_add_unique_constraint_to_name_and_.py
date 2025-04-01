"""add unique constraint to name and version columns on agreement table

Revision ID: c85608c8ca98
Revises: 245365f3bad4
Create Date: 2020-04-06 16:47:32.094677

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c85608c8ca98"
down_revision = "245365f3bad4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_version_name", "agreement", ["version", "name"])


def downgrade():
    op.drop_constraint("uq_version_name", "agreement", type_="unique")
