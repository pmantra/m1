"""Add soft_deleted_at columns to all q&a tables

Revision ID: 4a7cf537683c
Revises: d557a58dfed1
Create Date: 2020-12-07 20:48:22.491862

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4a7cf537683c"
down_revision = "d557a58dfed1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "questionnaire", sa.Column("soft_deleted_at", sa.DateTime(), default=None)
    )
    op.add_column(
        "question_set", sa.Column("soft_deleted_at", sa.DateTime(), default=None)
    )
    op.add_column("question", sa.Column("soft_deleted_at", sa.DateTime(), default=None))
    op.add_column("answer", sa.Column("soft_deleted_at", sa.DateTime(), default=None))


def downgrade():
    op.drop_column("questionnaire", "soft_deleted_at")
    op.drop_column("question_set", "soft_deleted_at")
    op.drop_column("question", "soft_deleted_at")
    op.drop_column("answer", "soft_deleted_at")
