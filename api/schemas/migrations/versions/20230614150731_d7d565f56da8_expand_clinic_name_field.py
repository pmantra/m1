"""Expand clinic name field

Revision ID: d7d565f56da8
Revises: ef88aa5d8541
Create Date: 2023-06-14 15:07:31.380269+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d7d565f56da8"
down_revision = "ef88aa5d8541"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE fertility_clinic MODIFY name VARCHAR(100)")


def downgrade():
    op.execute("ALTER TABLE fertility_clinic MODIFY name VARCHAR(50)")
