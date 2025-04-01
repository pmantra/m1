"""add new reimbursement organization configuration flags

Revision ID: e54cfdd38fcb
Revises: c4927c62ecfd
Create Date: 2023-05-25 19:13:21.465158+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "e54cfdd38fcb"
down_revision = "c4927c62ecfd"
branch_labels = None
depends_on = None


class FertilityProgramTypes(enum.Enum):
    CARVE_OUT = "CARVE OUT"
    WRAP_AROUND = "WRAP AROUND"


def upgrade():
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column("direct_payment_enabled", sa.Boolean, nullable=False, default=False),
    )
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column(
            "deductible_accumulation_enabled", sa.Boolean, nullable=False, default=False
        ),
    )
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column("closed_network", sa.Boolean, nullable=False, default=False),
    )
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column(
            "fertility_program_type",
            sa.Enum(FertilityProgramTypes),
            nullable=False,
            default=FertilityProgramTypes.CARVE_OUT,
        ),
    )
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column(
            "fertility_requires_diagnosis", sa.Boolean, nullable=False, default=False
        ),
    )
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column(
            "fertility_allows_taxable", sa.Boolean, nullable=False, default=False
        ),
    )


def downgrade():
    op.drop_column("reimbursement_organization_settings", "direct_payment_enabled")
    op.drop_column(
        "reimbursement_organization_settings", "deductible_accumulation_enabled"
    )
    op.drop_column("reimbursement_organization_settings", "closed_network")
    op.drop_column("reimbursement_organization_settings", "fertility_program_type")
    op.drop_column(
        "reimbursement_organization_settings", "fertility_requires_diagnosis"
    )
    op.drop_column("reimbursement_organization_settings", "fertility_allows_taxable")
