"""ch43632 add alegeus_id to origanization_employee

Revision ID: 0055cdc21010
Revises: 163b8567bf7e
Create Date: 2021-07-14 16:02:31.366757+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0055cdc21010"
down_revision = "163b8567bf7e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization_employee", sa.Column("alegeus_id", sa.VARCHAR(30), nullable=True)
    )
    op.create_unique_constraint("alegeus_id", "organization_employee", ["alegeus_id"])


def downgrade():
    op.drop_constraint("alegeus_id", "organization_employee", type_="unique")
    op.drop_column("organization_employee", "alegeus_id")
