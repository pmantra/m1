"""OrganizationEmployee last census

Revision ID: 6debc08cbb94
Revises: 27526ef71ab6
Create Date: 2020-04-30 20:29:36.991191

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6debc08cbb94"
down_revision = "27526ef71ab6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization_employee", sa.Column("last_census", sa.DateTime, nullable=True)
    )

    op.create_index("idx_last_census", "organization_employee", ["last_census"])

    op.add_column("organization", sa.Column("last_census", sa.DateTime, nullable=True))


def downgrade():
    op.drop_index("idx_last_census", table_name="organization_employee")
    op.drop_column("organization_employee", "last_census")
    op.drop_column("organization", "last_census")
