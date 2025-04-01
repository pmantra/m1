"""Add num_cycles column

Revision ID: c73766ebfe2c
Revises: f188ab2d1bb8
Create Date: 2023-04-27 22:46:09.156992+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c73766ebfe2c"
down_revision = "f188ab2d1bb8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_organization_settings_allowed_category",
        sa.Column("num_cycles", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("reimbursement_organization_settings_allowed_category", "num_cycles")
