"""add lob to wallet reporting

Revision ID: 9de74a570042
Revises: 3dc40a813cd3
Create Date: 2023-10-12 21:37:19.406448+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9de74a570042"
down_revision = "3dc40a813cd3"
branch_labels = None
depends_on = None


class OldColumnTypes(enum.Enum):
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
    LINE_OF_BUSINESS = "LINE_OF_BUSINESS"


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
