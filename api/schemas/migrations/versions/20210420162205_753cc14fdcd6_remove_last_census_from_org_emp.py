"""Remove last_census from org_emp

Revision ID: 753cc14fdcd6
Revises: 31579ad01055
Create Date: 2021-04-20 16:22:05.914646+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "753cc14fdcd6"
down_revision = "31579ad01055"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("idx_last_census", table_name="organization_employee")
    op.drop_column("organization_employee", "last_census")
    op.drop_column("organization", "last_census")


def downgrade():
    op.add_column(
        "organization_employee", sa.Column("last_census", sa.DateTime, nullable=True)
    )

    op.create_index("idx_last_census", "organization_employee", ["last_census"])

    op.add_column("organization", sa.Column("last_census", sa.DateTime, nullable=True))
