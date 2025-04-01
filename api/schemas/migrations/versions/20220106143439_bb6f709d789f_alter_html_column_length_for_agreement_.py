"""Alter html column length for Agreement table

Revision ID: bb6f709d789f
Revises: d4d9af2d349d
Create Date: 2022-01-06 14:34:39.775739+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


# revision identifiers, used by Alembic.
revision = "bb6f709d789f"
down_revision = "2d7ca1336374"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "agreement",
        "html",
        type_=MEDIUMTEXT,
        existing_type=sa.Text,
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "agreement",
        "html",
        type_=sa.Text,
        existing_type=MEDIUMTEXT,
        nullable=False,
    )
