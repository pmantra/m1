"""Clean up url_redirect table

Revision ID: 9bcb08116083
Revises: f0c9620948af
Create Date: 2022-05-24 15:35:26.835699+00:00

"""
from alembic import op
import sqlalchemy as sa

from storage.connection import db


# revision identifiers, used by Alembic.
revision = "9bcb08116083"
down_revision = "f0c9620948af"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("url_redirect_ibfk_2", "url_redirect", type_="foreignkey")
    op.alter_column(
        "url_redirect", "dest_url_path_id", existing_type=sa.Integer, nullable=False
    )
    op.create_foreign_key(
        "url_redirect_ibfk_2",
        "url_redirect",
        "url_redirect_path",
        ["dest_url_path_id"],
        ["id"],
    )

    op.drop_column("url_redirect", "dest_url_path")


def downgrade():
    op.drop_constraint("url_redirect_ibfk_2", "url_redirect", type_="foreignkey")
    op.alter_column(
        "url_redirect", "dest_url_path_id", existing_type=sa.Integer, nullable=True
    )
    op.create_foreign_key(
        "url_redirect_ibfk_2",
        "url_redirect",
        "url_redirect_path",
        ["dest_url_path_id"],
        ["id"],
    )

    op.add_column(
        "url_redirect",
        sa.Column("dest_url_path", sa.VARCHAR(255), default=False, nullable=False),
    )
    db.session.execute(
        """
UPDATE url_redirect u
JOIN url_redirect_path urp ON u.dest_url_path_id = urp.id
SET u.dest_url_path = urp.path
"""
    )
    db.session.commit()
