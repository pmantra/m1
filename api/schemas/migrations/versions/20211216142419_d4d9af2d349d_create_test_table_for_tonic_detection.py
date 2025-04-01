"""Create test table for tonic detection

Revision ID: d4d9af2d349d
Revises: 026cfdc265c9
Create Date: 2021-12-16 14:24:19.441599+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4d9af2d349d"
down_revision = "026cfdc265c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "test_cats_are_cool",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255)),
    )


def downgrade():
    op.drop_table("test_cats_are_cool")
