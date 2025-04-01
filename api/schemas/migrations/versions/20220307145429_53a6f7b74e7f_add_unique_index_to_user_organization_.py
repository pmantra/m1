"""Add unique index to user_organization_employee table

Revision ID: 53a6f7b74e7f
Revises: 698005426cc9
Create Date: 2022-03-07 14:54:29.357322+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "53a6f7b74e7f"
down_revision = "698005426cc9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_user_org_employee",
        "user_organization_employee",
        ["user_id", "organization_employee_id"],
    )


def downgrade():
    op.drop_constraint(
        "user_organization_employee_ibfk_1",
        "user_organization_employee",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_user_org_employee", "user_organization_employee", type_="unique"
    )
    op.create_foreign_key(
        "user_organization_employee_ibfk_1",
        "user_organization_employee",
        "user",
        ["user_id"],
        ["id"],
    )
