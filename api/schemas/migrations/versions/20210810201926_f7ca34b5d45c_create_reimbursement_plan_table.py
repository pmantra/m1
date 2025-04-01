"""Create reimbursement_plan table

Revision ID: f7ca34b5d45c
Revises: 27e152002f9c
Create Date: 2021-08-10 20:19:26.183046+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7ca34b5d45c"
down_revision = "27e152002f9c"
branch_labels = None
depends_on = None


class AlegeusCovereageTier(enum.Enum):
    SINGLE = "SINGLE"
    FAMILY = "FAMILY"


class ReimbursementPlanType(enum.Enum):
    LIFETIME = "LIFETIME"
    ANNUAL = "ANNUAL"


def upgrade():
    op.create_table(
        "reimbursement_plan",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("alegeus_plan_id", sa.VARCHAR(50), nullable=True),
        sa.Column("deductible_amount", sa.Numeric(scale=2), nullable=True),
        sa.Column("is_hdhp", sa.Boolean, nullable=True),
        sa.Column(
            "alegeus_coverage_tier", sa.Enum(AlegeusCovereageTier), nullable=True
        ),
        sa.Column("auto_renew", sa.Boolean, nullable=True),
        sa.Column("plan_type", sa.Enum(ReimbursementPlanType), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
    )
    op.create_unique_constraint(
        "alegeus_plan_id", "reimbursement_plan", ["alegeus_plan_id"]
    )
    op.add_column(
        "reimbursement_request_category",
        sa.Column(
            "reimbursement_plan_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_plan.id"),
        ),
    )


def downgrade():
    op.drop_constraint("alegeus_plan_id", "reimbursement_plan", type_="unique")
    op.drop_constraint(
        "reimbursement_request_category_ibfk_1",
        "reimbursement_request_category",
        type_="foreignkey",
    )
    op.drop_column("reimbursement_plan", "alegeus_plan_id")
    op.drop_column("reimbursement_request_category", "reimbursement_plan_id")
    op.drop_table("reimbursement_plan")
