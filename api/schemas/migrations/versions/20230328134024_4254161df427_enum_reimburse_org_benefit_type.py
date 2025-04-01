"""enum_benefit_type

Revision ID: 4254161df427
Revises: 32a28e455e3b
Create Date: 2023-03-28 13:40:24.074549+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4254161df427"
down_revision = "32a28e455e3b"
branch_labels = None
depends_on = None


def upgrade():
    class BenefitTypes(enum.Enum):
        CURRENCY = "CURRENCY"
        CYCLE = "CYCLE"

    op.add_column(
        "reimbursement_organization_settings_allowed_category",
        sa.Column(
            "benefit_type",
            sa.Enum(BenefitTypes),
            nullable=False,
            default=BenefitTypes.CURRENCY,
        ),
    )


def downgrade():
    op.drop_column(
        "reimbursement_organization_settings_allowed_category", "benefit_type"
    )
