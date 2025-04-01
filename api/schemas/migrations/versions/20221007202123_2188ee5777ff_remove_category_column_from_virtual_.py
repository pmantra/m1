"""remove_category_column_from_virtual_event_table

Revision ID: 2188ee5777ff
Revises: 6b5504da7b0d
Create Date: 2022-10-07 20:21:23.570045+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2188ee5777ff"
down_revision = "6b5504da7b0d"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("virtual_event", "category")


def downgrade():
    op.add_column(
        "virtual_event", sa.Column("category", sa.String(128), nullable=False)
    )
