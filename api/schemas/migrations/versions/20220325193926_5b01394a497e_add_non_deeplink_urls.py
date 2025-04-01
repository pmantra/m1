"""Add non-deeplink urls

Revision ID: 5b01394a497e
Revises: e20f8aa43430
Create Date: 2022-03-25 19:39:26.940573+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b01394a497e"
down_revision = "e20f8aa43430"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ios_non_deeplink_urls",
        sa.Column("url", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("ios_non_deeplink_urls")
