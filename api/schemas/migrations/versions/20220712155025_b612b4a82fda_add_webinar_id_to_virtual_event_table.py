"""Add webinar_id to virtual_event table

Revision ID: b612b4a82fda
Revises: 8923e4783291
Create Date: 2022-07-12 15:50:25.766782+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b612b4a82fda"
down_revision = "8923e4783291"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "virtual_event", sa.Column("webinar_id", sa.BigInteger, nullable=True)
    )


def downgrade():
    op.drop_column("virtual_event", "webinar_id")
