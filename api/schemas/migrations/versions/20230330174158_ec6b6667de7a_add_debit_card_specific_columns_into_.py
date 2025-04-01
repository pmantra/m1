"""add_debit_card_specific_columns_into_enum_for_wallet_reporting

Revision ID: ec6b6667de7a
Revises: 4254161df427
Create Date: 2023-03-30 17:41:58.355015+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ec6b6667de7a"
down_revision = "4254161df427"
branch_labels = None
depends_on = None


class OldWalletReportConfigColumnTypes(enum.Enum):
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


class NewWalletReportConfigColumnTypes(enum.Enum):
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


def upgrade():
    op.alter_column(
        "wallet_client_report_configuration_report_types",
        "column_type",
        type_=sa.Enum(NewWalletReportConfigColumnTypes),
        existing_type=sa.Enum(OldWalletReportConfigColumnTypes),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "wallet_client_report_configuration_report_types",
        "column_type",
        type_=sa.Enum(OldWalletReportConfigColumnTypes),
        existing_type=sa.Enum(NewWalletReportConfigColumnTypes),
        nullable=False,
    )
