"""Remove is_cancelled column from BMS order table

Revision ID: c6a589356068
Revises: fef8e76f6c36
Create Date: 2022-10-06 20:16:43.453506+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c6a589356068"
down_revision = "4d99c216f8b6"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("bms_order", "is_cancelled")


def downgrade():
    op.add_column(
        "bms_order",
        sa.Column("is_cancelled", sa.Boolean, nullable=False, default=False),
    )
