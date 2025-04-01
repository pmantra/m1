"""create-table-need-specialty

Revision ID: c24241a5dd26
Revises: a087c7db5e8b
Create Date: 2023-02-24 03:35:40.008273+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c24241a5dd26"
down_revision = "a087c7db5e8b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "needs_specialty",
        sa.Column(
            "specialty_id", sa.Integer, sa.ForeignKey("specialty.id"), primary_key=True
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
        "needs_specialty_keyword",
        sa.Column(
            "keyword_id",
            sa.Integer,
            sa.ForeignKey("specialty_keyword.id"),
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
    op.drop_table("needs_specialty")
    op.drop_table("needs_specialty_keyword")
