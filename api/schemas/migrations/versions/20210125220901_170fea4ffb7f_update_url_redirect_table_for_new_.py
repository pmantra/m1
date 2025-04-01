"""update url_redirect table for new landing pages

Revision ID: 170fea4ffb7f
Revises: 99ca62d89a72
Create Date: 2021-01-25 22:09:01.551513

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "170fea4ffb7f"
down_revision = "99ca62d89a72"
branch_labels = None
depends_on = None

new_type = sa.String(255)
old_type = sa.Enum(
    "maternity-signup",
    "maternity-egg-freezing-signup",
    "maven-maternity-signup",
    "maven-maternity-benefit-signup",
    "maven-fertility-signup",
)


def upgrade():
    op.alter_column(
        "url_redirect",
        "dest_url_path",
        type_=new_type,
        existing_type=old_type,
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "url_redirect",
        "dest_url_path",
        type_=old_type,
        existing_type=new_type,
        nullable=False,
    )
