"""Add host image and name to virtual events

Revision ID: bf345a0650e9
Revises: 2897111590c0
Create Date: 2021-06-24 21:01:39.306849+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bf345a0650e9"
down_revision = "2897111590c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "virtual_event", sa.Column("host_image_url", sa.String(1024), nullable=True)
    )
    op.add_column(
        "virtual_event", sa.Column("host_name", sa.String(256), nullable=True)
    )


def downgrade():
    op.drop_column("virtual_event", "host_image_url")
    op.drop_column("virtual_event", "host_name")
