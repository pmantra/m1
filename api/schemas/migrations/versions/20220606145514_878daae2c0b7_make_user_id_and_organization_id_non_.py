"""Make user_id and organization_id non nullable

Revision ID: 878daae2c0b7
Revises: 954ad4fed0a0
Create Date: 2022-06-06 14:55:14.142022+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "878daae2c0b7"
down_revision = "954ad4fed0a0"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "user_organization_employee_ibfk_1",
        "user_organization_employee",
        type_="foreignkey",
    )
    op.alter_column(
        "user_organization_employee",
        "user_id",
        existing_type=sa.Integer,
        nullable=False,
    )
    op.create_foreign_key(
        "user_organization_employee_ibfk_1",
        "user_organization_employee",
        "user",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(
        "user_organization_employee_ibfk_2",
        "user_organization_employee",
        type_="foreignkey",
    )
    op.alter_column(
        "user_organization_employee",
        "organization_employee_id",
        existing_type=sa.Integer,
        nullable=False,
    )
    op.create_foreign_key(
        "user_organization_employee_ibfk_2",
        "user_organization_employee",
        "organization_employee",
        ["organization_employee_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "user_organization_employee_ibfk_1",
        "user_organization_employee",
        type_="foreignkey",
    )
    op.alter_column(
        "user_organization_employee", "user_id", existing_type=sa.Integer, nullable=True
    )
    op.create_foreign_key(
        "user_organization_employee_ibfk_1",
        "user_organization_employee",
        "user",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(
        "user_organization_employee_ibfk_2",
        "user_organization_employee",
        type_="foreignkey",
    )
    op.alter_column(
        "user_organization_employee",
        "organization_employee_id",
        existing_type=sa.Integer,
        nullable=True,
    )
    op.create_foreign_key(
        "user_organization_employee_ibfk_2",
        "user_organization_employee",
        "organization_employee",
        ["organization_employee_id"],
        ["id"],
    )
