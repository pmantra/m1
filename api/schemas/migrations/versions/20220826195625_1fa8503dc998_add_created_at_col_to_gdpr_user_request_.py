"""Add created_at col to gdpr user request table


Revision ID: 1fa8503dc998
Revises: 1a2340ec21dd
Create Date: 2022-08-26 19:56:25.889043+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1fa8503dc998"
down_revision = "7079b9fa4d38"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gdpr_user_request", sa.Column("created_at", sa.DateTime))


def downgrade():
    op.drop_column("gdpr_user_request", "created_at")
