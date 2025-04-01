"""Create URL redirect paths table

Revision ID: 08fe07727ef7
Revises: 617f132a201a
Create Date: 2022-05-13 18:29:48.023789+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "08fe07727ef7"
down_revision = "e070e7a507e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "url_redirect_path",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("path", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )

    # Add new foreign key column to the `url_redirect` table.
    # NOTE: the existing `url_redirect.dest_url_path` column will be removed in a follow-up migration.
    op.add_column(
        "url_redirect",
        sa.Column(
            "dest_url_path_id", sa.Integer, sa.ForeignKey("url_redirect_path.id")
        ),
    )


def downgrade():
    op.drop_constraint("url_redirect_ibfk_2", "url_redirect", type_="foreignkey")
    op.drop_column("url_redirect", "dest_url_path_id")
    op.drop_table("url_redirect_path")
