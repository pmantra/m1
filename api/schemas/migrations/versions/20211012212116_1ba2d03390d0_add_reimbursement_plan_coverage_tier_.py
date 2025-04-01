"""Add reimbursement_plan_coverage_tier table

Revision ID: 1ba2d03390d0
Revises: ed68860d80b3
Create Date: 2021-10-12 21:21:16.637902+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1ba2d03390d0"
down_revision = "ed68860d80b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_plan_coverage_tier",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("single_amount", sa.Numeric(scale=2), nullable=True),
        sa.Column("family_amount", sa.Numeric(scale=2), nullable=True),
    )
    op.add_column(
        "reimbursement_plan",
        sa.Column(
            "reimbursement_plan_coverage_tier_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_plan_coverage_tier.id"),
        ),
    )


def downgrade():
    op.drop_constraint(
        "reimbursement_plan_ibfk_2", "reimbursement_plan", type_="foreignkey"
    )
    op.drop_column("reimbursement_plan", "reimbursement_plan_coverage_tier_id")
    op.drop_table("reimbursement_plan_coverage_tier")
