"""update employee health plan to integer amounts

Revision ID: 00b675e0cdeb
Revises: b1228056a304
Create Date: 2023-05-05 16:43:36.053517+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "00b675e0cdeb"
down_revision = "b1228056a304"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "employee_health_plan",
        "deductible",
        type_=sa.Integer,
        existing_type=sa.Numeric(precision=7, scale=2),
        nullable=False,
    )
    op.alter_column(
        "employee_health_plan",
        "max_out_of_pocket",
        type_=sa.Integer,
        existing_type=sa.Numeric(precision=7, scale=2),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "employee_health_plan",
        "deductible",
        type_=sa.Numeric(precision=7, scale=2),
        existing_type=sa.Integer,
        nullable=False,
    )
    op.alter_column(
        "employee_health_plan",
        "max_out_of_pocket",
        type_=sa.Numeric(precision=7, scale=2),
        existing_type=sa.Integer,
        nullable=False,
    )
