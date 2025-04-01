"""Add Resource WebFlow URL

Revision ID: 1e76c90159ca
Revises: 6debc08cbb94
Create Date: 2020-04-22 15:35:27.357241

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1e76c90159ca"
down_revision = "6debc08cbb94"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("resource", sa.Column("webflow_url", sa.String(512), nullable=True))


def downgrade():
    op.drop_column("resource", "webflow_url")
