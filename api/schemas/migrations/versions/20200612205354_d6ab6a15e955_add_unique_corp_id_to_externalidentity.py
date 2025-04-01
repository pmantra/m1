"""Add unique_corp_id to ExternalIdentity

Revision ID: d6ab6a15e955
Revises: 5e354d543243
Create Date: 2020-06-12 20:53:54.690626

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d6ab6a15e955"
down_revision = "5e354d543243"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("external_identity", sa.Column("unique_corp_id", sa.String(120)))


def downgrade():
    op.drop_column("external_identity", "unique_corp_id")
