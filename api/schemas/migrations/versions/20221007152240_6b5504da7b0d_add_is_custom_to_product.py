"""add_is_custom_to_product

Revision ID: 6b5504da7b0d
Revises: c6a589356068
Create Date: 2022-10-07 15:22:40.302869+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6b5504da7b0d"
down_revision = "c6a589356068"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "product",
        sa.Column("is_custom", sa.Boolean, nullable=False, default=False),
    )


def downgrade():
    op.drop_column("product", "is_custom")
