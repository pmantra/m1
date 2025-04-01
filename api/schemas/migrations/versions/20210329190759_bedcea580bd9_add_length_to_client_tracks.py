"""add_length_to_client_tracks

Revision ID: bedcea580bd9
Revises: 4c4020e7b5a2
Create Date: 2021-03-29 19:07:59.861464

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bedcea580bd9"
down_revision = "4c4020e7b5a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "client_track", sa.Column("length_in_days", sa.Integer, nullable=True)
    )


def downgrade():
    op.drop_column("client_track", "length_in_days")
