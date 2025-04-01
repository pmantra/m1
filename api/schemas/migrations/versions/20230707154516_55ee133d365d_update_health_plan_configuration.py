"""update health plan configuration

Revision ID: 55ee133d365d
Revises: 633791ae4e12
Create Date: 2023-07-07 15:45:16.452888+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "55ee133d365d"
down_revision = "633791ae4e12"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("employee_health_plan", "deductible")
    op.drop_column("employee_health_plan", "max_out_of_pocket")

    op.add_column(
        "employer_health_plan",
        sa.Column("ind_deductible_limit", sa.Integer, nullable=False),
    )
    op.add_column(
        "employer_health_plan",
        sa.Column("ind_oop_max_limit", sa.Integer, nullable=False),
    )
    op.add_column(
        "employer_health_plan",
        sa.Column("fam_deductible_limit", sa.Integer, nullable=False),
    )
    op.add_column(
        "employer_health_plan",
        sa.Column("fam_oop_max_limit", sa.Integer, nullable=False),
    )


def downgrade():
    op.drop_column("employer_health_plan", "ind_deductible_limit")
    op.drop_column("employer_health_plan", "ind_oop_max_limit")
    op.drop_column("employer_health_plan", "fam_deductible_limit")
    op.drop_column("employer_health_plan", "fam_oop_max_limit")

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
