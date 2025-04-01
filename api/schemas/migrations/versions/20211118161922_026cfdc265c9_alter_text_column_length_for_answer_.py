"""Alter text column length for answer table

Revision ID: 026cfdc265c9
Revises: 584e2adddf63
Create Date: 2021-11-18 16:19:22.612357+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "026cfdc265c9"
down_revision = "584e2adddf63"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "answer",
        "text",
        type_=sa.String(6000),
        existing_type=sa.String(1000),
        nullable=True,
    )
    op.alter_column(
        "recorded_answer",
        "text",
        type_=sa.String(6000),
        existing_type=sa.String(1000),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "answer",
        "text",
        type_=sa.String(1000),
        existing_type=sa.String(6000),
        nullable=True,
    )
    op.alter_column(
        "recorded_answer",
        "text",
        type_=sa.String(1000),
        existing_type=sa.String(6000),
        nullable=True,
    )
