"""Require virtual_event_category_id on table virtual_event

Revision ID: 212848e165b7
Revises: 39147f439620
Create Date: 2022-06-14 17:53:43.426477+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "212848e165b7"
down_revision = "39147f439620"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("category_fk", "virtual_event", type_="foreignkey")
    op.alter_column(
        "virtual_event",
        "virtual_event_category_id",
        existing_type=sa.Integer,
        nullable=False,
    )
    op.create_foreign_key(
        "category_fk",
        "virtual_event",
        "virtual_event_category",
        ["virtual_event_category_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("category_fk", "virtual_event", type_="foreignkey")
    op.alter_column(
        "virtual_event",
        "virtual_event_category_id",
        existing_type=sa.Integer,
        nullable=True,
    )
    op.create_foreign_key(
        "category_fk",
        "virtual_event",
        "virtual_event_category",
        ["virtual_event_category_id"],
        ["id"],
    )
