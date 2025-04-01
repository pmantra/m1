"""Remove test-cats-are-cool

Revision ID: ccf79c3d408b
Revises: 3498601e7439
Create Date: 2023-06-02 04:11:47.455605+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ccf79c3d408b"
down_revision = "3498601e7439"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("test_cats_are_cool")


def downgrade():
    op.create_table(
        "test_cats_are_cool",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255)),
    )
