"""Add modified_at cols to gdpr user request table

Revision ID: 5ed17d0000e5
Revises: 1f83bf5d74d9
Create Date: 2022-08-22 19:51:53.401486+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5ed17d0000e5"
down_revision = "091593868639"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gdpr_user_request", sa.Column("modified_at", sa.DateTime))


def downgrade():
    op.drop_column("gdpr_user_request", "modified_at")
