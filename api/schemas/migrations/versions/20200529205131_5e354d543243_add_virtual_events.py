"""Add virtual events

Revision ID: 5e354d543243
Revises: a03d9557c069
Create Date: 2020-05-29 20:51:31.087826

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5e354d543243"
down_revision = "a03d9557c069"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "virtual_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("registration_form_url", sa.String(255), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("scheduled_start", sa.DateTime, nullable=False),
        sa.Column("scheduled_end", sa.DateTime, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("virtual_event")
