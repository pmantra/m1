"""add created_at and modified_at to external_identity table

Revision ID: 204aba110c60
Revises: 3c8e19bfe944
Create Date: 2022-09-12 14:27:30.599826+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "204aba110c60"
down_revision = "3c8e19bfe944"
branch_labels = None
depends_on = None
TABLE_NAME = "external_identity"


def upgrade():
    op.add_column(TABLE_NAME, sa.Column("modified_at", sa.DateTime))
    op.add_column(TABLE_NAME, sa.Column("created_at", sa.DateTime))


def downgrade():
    op.drop_column(TABLE_NAME, "modified_at")
    op.drop_column(TABLE_NAME, "created_at")
