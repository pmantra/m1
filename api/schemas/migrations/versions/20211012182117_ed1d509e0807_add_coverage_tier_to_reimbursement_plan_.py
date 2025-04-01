"""Add coverage tier to Reimbursement Plan HDHP

Revision ID: ed1d509e0807
Revises: ed68860d80b3
Create Date: 2021-10-12 18:21:17.759617+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.constants import AlegeusCoverageTier


# revision identifiers, used by Alembic.
revision = "ed1d509e0807"
down_revision = "1ba2d03390d0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_wallet_plan_hdhp",
        sa.Column(
            "alegeus_coverage_tier", sa.Enum(AlegeusCoverageTier), nullable=False
        ),
    )
    op.drop_column("reimbursement_wallet_plan_hdhp", "start_date")
    op.drop_column("reimbursement_wallet_plan_hdhp", "end_date")


def downgrade():
    op.drop_column("reimbursement_wallet_plan_hdhp", "alegeus_coverage_tier")

    op.add_column(
        "reimbursement_wallet_plan_hdhp",
        sa.Column("start_date", sa.Date, nullable=True),
    )
    op.add_column(
        "reimbursement_wallet_plan_hdhp", sa.Column("end_date", sa.Date, nullable=True)
    )
