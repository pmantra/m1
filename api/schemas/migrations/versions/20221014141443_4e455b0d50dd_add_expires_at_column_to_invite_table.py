"""add_expires_at_column_to_invite_table

Revision ID: 4e455b0d50dd
Revises: ba9c788ac7c1
Create Date: 2022-10-14 14:14:43.675578+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4e455b0d50dd"
down_revision = "ba9c788ac7c1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invite", sa.Column("expires_at", sa.DateTime, nullable=True))


def downgrade():
    op.drop_column("invite", "expires_at")
