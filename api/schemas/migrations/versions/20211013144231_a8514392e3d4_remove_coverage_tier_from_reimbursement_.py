"""Remove coverage tier from reimbursement plan

Revision ID: a8514392e3d4
Revises: ed1d509e0807
Create Date: 2021-10-13 14:42:31.263958+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from wallet.models.constants import AlegeusCoverageTier

revision = "a8514392e3d4"
down_revision = "ed1d509e0807"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("reimbursement_plan", "alegeus_coverage_tier")
    op.drop_column("reimbursement_plan", "deductible_amount")


def downgrade():
    op.add_column(
        "reimbursement_plan",
        sa.Column("alegeus_coverage_tier", sa.Enum(AlegeusCoverageTier), nullable=True),
    )
    op.add_column(
        "reimbursement_plan",
        sa.Column("deductible_amount", sa.Numeric(scale=2), nullable=True),
    )
