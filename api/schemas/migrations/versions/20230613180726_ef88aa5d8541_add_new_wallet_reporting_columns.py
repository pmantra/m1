"""add new wallet reporting columns

Revision ID: ef88aa5d8541
Revises: d3d571d8c873
Create Date: 2023-06-13 18:07:26.521618+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ef88aa5d8541"
down_revision = "d3d571d8c873"
branch_labels = None
depends_on = None


class OldColumnTypes(enum.Enum):
    PROGRAM = "PROGRAM"
    VALUE_TO_APPROVE = "VALUE_TO_APPROVE"
    FX_RATE = "FX_RATE"
    VALUE_TO_APPROVE_USD = "VALUE_TO_APPROVE_USD"
    PRIOR_PROGRAM_TO_DATE = "PRIOR_PROGRAM_TO_DATE"
    TOTAL_PROGRAM_TO_DATE = "TOTAL_PROGRAM_TO_DATE"
    REIMBURSEMENT_TYPE = "REIMBURSEMENT_TYPE"
    COUNTRY = "COUNTRY"
    TAXATION = "TAXATION"
    PAYROLL_DEPT = "PAYROLL_DEPT"
    DEBIT_CARD_FUND_USAGE_USD = "DEBIT_CARD_FUND_USAGE_USD"
    DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION = "DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION"


class NewColumnTypes(enum.Enum):
    EMPLOYEE_ID = "EMPLOYEE_ID"
    EMPLOYER_ASSIGNED_ID = "EMPLOYER_ASSIGNED_ID"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    FIRST_NAME = "FIRST_NAME"
    LAST_NAME = "LAST_NAME"
    PROGRAM = "PROGRAM"
    VALUE_TO_APPROVE = "VALUE_TO_APPROVE"
    FX_RATE = "FX_RATE"
    VALUE_TO_APPROVE_USD = "VALUE_TO_APPROVE_USD"
    PRIOR_PROGRAM_TO_DATE = "PRIOR_PROGRAM_TO_DATE"
    TOTAL_PROGRAM_TO_DATE = "TOTAL_PROGRAM_TO_DATE"
    REIMBURSEMENT_TYPE = "REIMBURSEMENT_TYPE"
    COUNTRY = "COUNTRY"
    TAXATION = "TAXATION"
    PAYROLL_DEPT = "PAYROLL_DEPT"
    DEBIT_CARD_FUND_USAGE_USD = "DEBIT_CARD_FUND_USAGE_USD"
    DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION = "DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION"
    TOTAL_FUNDS_FOR_TAX_HANDLING = "TOTAL_FUNDS_FOR_TAX_HANDLING"


def upgrade():
    op.alter_column(
        "wallet_client_report_configuration_report_types",
        "column_type",
        type_=sa.Enum(NewColumnTypes),
        existing_type=sa.Enum(OldColumnTypes),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "wallet_client_report_configuration_report_types",
        "column_type",
        type_=sa.Enum(OldColumnTypes),
        existing_type=sa.Enum(NewColumnTypes),
        nullable=False,
    )
