"""add columns to language

Revision ID: 302b1f090e11
Revises: 74ea90de1a7a
Create Date: 2022-07-28 17:41:13.023574+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "302b1f090e11"
down_revision = "74ea90de1a7a"

branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "language",
        sa.Column("abbreviation", sa.String(10), nullable=True),
    )
    op.add_column(
        "language",
        sa.Column("iso-639-3", sa.String(10), nullable=True),
    )
    op.add_column(
        "language",
        sa.Column("inverted_name", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("language", "abbreviation")
    op.drop_column("language", "iso-639-3")
    op.drop_column("language", "inverted_name")
