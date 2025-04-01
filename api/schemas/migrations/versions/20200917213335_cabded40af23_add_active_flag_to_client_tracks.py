"""Add active flag to client tracks

Revision ID: cabded40af23
Revises: 9504a13254e5
Create Date: 2020-09-17 21:33:35.746549

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cabded40af23"
down_revision = "9504a13254e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "client_track", sa.Column("active", sa.Boolean, default=True, nullable=False)
    )


def downgrade():
    op.drop_column("client_track", "active")
