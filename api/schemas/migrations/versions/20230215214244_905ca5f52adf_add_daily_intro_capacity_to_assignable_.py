"""add daily_intro_capacity to assignable_advocate

Revision ID: 905ca5f52adf
Revises: 7632237e43f0
Create Date: 2023-02-15 21:42:44.853413+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "905ca5f52adf"
down_revision = "7632237e43f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assignable_advocate",
        sa.Column("daily_intro_capacity", sa.SmallInteger, nullable=True),
    )


def downgrade():
    op.drop_column("assignable_advocate", "daily_intro_capacity")
