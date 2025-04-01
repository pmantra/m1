"""add direct payment fund usage to wallet reporting

Revision ID: 0003f27a5541
Revises: 6219ce1fefcf
Create Date: 2023-11-07 19:15:09.831455+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum

# revision identifiers, used by Alembic.
revision = "0003f27a5541"
down_revision = "0a3abe7b58b5"
branch_labels = None
depends_on = None


class ColumnTypesV1(enum.Enum):
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
    LINE_OF_BUSINESS = "LINE_OF_BUSINESS"


class ColumnTypesV2(enum.Enum):
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
    LINE_OF_BUSINESS = "LINE_OF_BUSINESS"
    DIRECT_PAYMENT_FUND_USAGE = "DIRECT_PAYMENT_FUND_USAGE"


def upgrade():
    op.alter_column(
        "wallet_client_report_configuration_report_types",
        "column_type",
        type_=sa.Enum(ColumnTypesV2),
        existing_type=sa.Enum(ColumnTypesV1),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "wallet_client_report_configuration_report_types",
        "column_type",
        type_=sa.Enum(ColumnTypesV1),
        existing_type=sa.Enum(ColumnTypesV2),
        nullable=False,
    )
