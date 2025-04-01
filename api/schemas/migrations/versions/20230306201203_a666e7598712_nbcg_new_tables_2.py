"""nbcg-new-tables-2

Revision ID: a666e7598712
Revises: 919cd4e12d91
Create Date: 2023-03-06 20:12:03.277695+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a666e7598712"
down_revision = "919cd4e12d91"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "needs_category",
        sa.Column(
            "category_id", sa.Integer, sa.ForeignKey("category.id"), primary_key=True
        ),
        sa.Column(
            "needs_id",
            sa.Integer,
            sa.ForeignKey("needs.id"),
            primary_key=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )

    op.create_table(
        "needs_vertical",
        sa.Column(
            "vertical_id",
            sa.Integer,
            sa.ForeignKey("vertical.id"),
            primary_key=True,
        ),
        sa.Column(
            "needs_id",
            sa.Integer,
            sa.ForeignKey("needs.id"),
            primary_key=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("needs_category")
    op.drop_table("needs_vertical")
