"""Add max_capacity to assignable_advocate table

Revision ID: a7dba4ca6947
Revises: f500a6bcc00d
Create Date: 2021-04-14 14:52:07.103212+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7dba4ca6947"
down_revision = "f500a6bcc00d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assignable_advocate", sa.Column("max_capacity", sa.SmallInteger, nullable=True)
    )


def downgrade():
    op.drop_column("assignable_advocate", "max_capacity")
