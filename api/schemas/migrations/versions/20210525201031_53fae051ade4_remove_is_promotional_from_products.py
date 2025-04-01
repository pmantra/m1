"""remove is_promotional from products

Revision ID: 53fae051ade4
Revises: 3ad95c89fad8
Create Date: 2021-05-25 20:10:31.030166+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "53fae051ade4"
down_revision = "2dedc9203107"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("product", "is_promotional")


def downgrade():
    op.add_column("product", sa.Column("is_promotional", sa.Boolean))
