"""move deductible and max from employer to employee health plan

Revision ID: 31a64daa2bf6
Revises: 3ac121518956
Create Date: 2023-05-01 18:04:48.144360+00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "31a64daa2bf6"
down_revision = "331494abfe04"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("employer_health_plan", "deductible")
    op.drop_column("employer_health_plan", "max_out_of_pocket")

    op.add_column(
        "employee_health_plan",
        sa.Column("deductible", sa.Numeric(precision=7, scale=2), nullable=False),
    )
    op.add_column(
        "employee_health_plan",
        sa.Column(
            "max_out_of_pocket", sa.Numeric(precision=7, scale=2), nullable=False
        ),
    )


def downgrade():
    op.add_column(
        "employer_health_plan",
        sa.Column("deductible", sa.Numeric(precision=7, scale=2), nullable=False),
    )

    op.add_column(
        "employer_health_plan",
        sa.Column(
            "max_out_of_pocket", sa.Numeric(precision=7, scale=2), nullable=False
        ),
    )

    op.drop_column("employee_health_plan", "deductible")
    op.drop_column("employee_health_plan", "max_out_of_pocket")
