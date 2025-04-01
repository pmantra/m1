"""Create employer and employee health plan tables

Revision ID: 71e8c9a36b8e
Revises: ec6b6667de7a
Create Date: 2023-04-03 22:20:21.136535+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "71e8c9a36b8e"
down_revision = "03a20c617bee"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employer_health_plan",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_org_settings_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_organization_settings.id"),
            nullable=False,
        ),
        sa.Column("deductible", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column(
            "max_out_of_pocket", sa.Numeric(precision=7, scale=2), nullable=False
        ),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
    )

    class CostSharingType(enum.Enum):
        COPAY = "COPAY"
        COINSURANCE = "COINSURANCE"

    class CostSharingCategory(enum.Enum):
        OFFICE_VISITS = "OFFICE_VISITS"
        PRESCRIPTIONS = "PRESCRIPTIONS"
        DIAGNOSTIC_IMAGES = "DIAGNOSTIC_IMAGES"

    op.create_table(
        "employer_health_plan_cost_sharing",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "employer_health_plan_id",
            sa.BigInteger,
            sa.ForeignKey("employer_health_plan.id"),
            nullable=False,
        ),
        sa.Column("cost_sharing_type", sa.Enum(CostSharingType), nullable=False),
        sa.Column(
            "cost_sharing_category", sa.Enum(CostSharingCategory), nullable=False
        ),
        sa.Column("dollar_amount", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("percent", sa.Numeric(precision=5, scale=2), nullable=True),
    )

    class HealthPlanType(enum.Enum):
        GENERIC = "GENERIC"
        HDHP = "HDHP"

    class PatientAndSubscriberRelationship(enum.Enum):
        SELF = "SELF"
        SPOUSE = "SPOUSE"
        PARTNER = "PARTNER"
        DEPENDENT = "DEPENDENT"

    op.create_table(
        "employee_health_plan",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "employer_health_plan_id",
            sa.BigInteger,
            sa.ForeignKey("employer_health_plan.id"),
            nullable=True,
        ),
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_wallet.id"),
            nullable=False,
        ),
        sa.Column("patient_first_name", sa.String(50), nullable=False),
        sa.Column("patient_last_name", sa.String(50), nullable=False),
        sa.Column("patient_plan_name", sa.String(50), nullable=False),
        sa.Column("patient_date_of_birth", sa.Date, nullable=False),
        sa.Column("subscriber_insurance_id", sa.String(50), nullable=False),
        sa.Column("patient_insurance_id", sa.String(50), nullable=False),
        sa.Column("plan_type", sa.Enum(HealthPlanType), nullable=False),
        sa.Column(
            "relationship", sa.Enum(PatientAndSubscriberRelationship), nullable=False
        ),
    )


def downgrade():
    op.drop_table("employee_health_plan")
    op.drop_table("employer_health_plan_cost_sharing")
    op.drop_table("employer_health_plan")
