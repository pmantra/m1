"""Remove assessment phases

Revision ID: 7dc1f518a2df
Revises: 24b2f99e93e4
Create Date: 2020-10-03 03:06:39.810371

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7dc1f518a2df"
down_revision = "24b2f99e93e4"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("assessment_phases")


def downgrade():
    pass
