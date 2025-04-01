"""change cost sharing categories enum

Revision ID: b064ab44c011
Revises: 632b5a4e768e
Create Date: 2023-07-31 19:43:06.025834+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b064ab44c011"
down_revision = "632b5a4e768e"
branch_labels = None
depends_on = None


def upgrade():
    class CostSharingCategory(enum.Enum):
        CONSULTATION = "3"
        MEDICAL_CARE = "30"
        DIAGNOSTIC_MEDICAL = "73"

    op.drop_column("employer_health_plan_cost_sharing", "cost_sharing_category")
    op.add_column(
        "employer_health_plan_cost_sharing",
        sa.Column(
            "cost_sharing_category",
            sa.Enum(CostSharingCategory),
            nullable=False,
        ),
    )


def downgrade():
    class CostSharingCategory(enum.Enum):
        OFFICE_VISITS = "OFFICE_VISITS"
        PRESCRIPTIONS = "PRESCRIPTIONS"
        DIAGNOSTIC_IMAGES = "DIAGNOSTIC_IMAGES"

    op.drop_column("employer_health_plan_cost_sharing", "cost_sharing_category")
    op.add_column(
        "employer_health_plan_cost_sharing",
        sa.Column(
            "cost_sharing_category",
            sa.Enum(CostSharingCategory),
            nullable=False,
        ),
    )
