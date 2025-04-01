"""treatment_procedure_cost_breakdown_infertility_diagnosis

Revision ID: 74be3169efe3
Revises: b064ab44c011
Create Date: 2023-08-04 16:42:10.164848+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.constants import PatientInfertilityDiagnosis


# revision identifiers, used by Alembic.
revision = "74be3169efe3"
down_revision = "4ee33fc3ab51"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "treatment_procedure",
        sa.Column("cost_breakdown_id", sa.Integer, nullable=True),
    )

    op.add_column(
        "treatment_procedure",
        sa.Column(
            "infertility_diagnosis",
            sa.Enum(PatientInfertilityDiagnosis),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("treatment_procedure", "cost_breakdown_id")
    op.drop_column("treatment_procedure", "infertility_diagnosis")
