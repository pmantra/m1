"""Remove unique constraint on organization_employee.email

Revision ID: 03c83a319162
Revises: f457f4b4eac2
Create Date: 2021-02-22 19:03:46.020550

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "03c83a319162"
down_revision = "f457f4b4eac2"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("email", "organization_employee", type_="unique")
    op.create_index("idx_email", "organization_employee", ["email"])


def downgrade():
    op.drop_index("idx_email", "organization_employee")
    op.create_unique_constraint("email", "organization_employee", ["email"])
