import enum

from wallet.models.constants import (
    ReimbursementRequestState,
    WalletReportConfigColumnTypes,
)

UNSUBSTANTIATED_DEBIT_COLS_OMIT = {
    WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD.name,
    WalletReportConfigColumnTypes.FX_RATE.name,
    WalletReportConfigColumnTypes.TOTAL_FUNDS_FOR_TAX_HANDLING.name,
    WalletReportConfigColumnTypes.VALUE_TO_APPROVE.name,
    WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD.name,
}
UNSUBSTANTIATED_DEBIT_REIMBURSEMENT_STATES = [
    ReimbursementRequestState.NEEDS_RECEIPT,
    ReimbursementRequestState.INSUFFICIENT_RECEIPT,
    ReimbursementRequestState.RECEIPT_SUBMITTED,
]

REPORT_REIMBURSEMENT_STATES = [
    ReimbursementRequestState.APPROVED,
    ReimbursementRequestState.REFUNDED,
]
NEW_REPORT_QUERY_REIMBURSEMENT_STATES = [
    ReimbursementRequestState.APPROVED,
    ReimbursementRequestState.REFUNDED,
    ReimbursementRequestState.INELIGIBLE_EXPENSE,
]

YTD_REPORT_REIMBURSEMENT_STATES = [
    ReimbursementRequestState.APPROVED,
    ReimbursementRequestState.REFUNDED,
    ReimbursementRequestState.INELIGIBLE_EXPENSE,
    ReimbursementRequestState.REIMBURSED,
    ReimbursementRequestState.RESOLVED,
]

# Ordering here determines the order in which columns are listed in the report.
# Since dict order is preserved and is constant, we can safely use this to format our column order.
WALLET_REPORT_COLUMN_NAMES = {
    WalletReportConfigColumnTypes.EMPLOYEE_ID.name: "Employee ID",
    WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID.name: "Employer Assigned ID",
    WalletReportConfigColumnTypes.DATE_OF_BIRTH.name: "Date of Birth",
    WalletReportConfigColumnTypes.FIRST_NAME.name: "First Name",
    WalletReportConfigColumnTypes.LAST_NAME.name: "Last Name",
    WalletReportConfigColumnTypes.PROGRAM.name: "Program",
    WalletReportConfigColumnTypes.VALUE_TO_APPROVE.name: "Reimbursements to be approved",
    WalletReportConfigColumnTypes.FX_RATE.name: "Fx Rate",
    WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD.name: "Reimbursements to be approved (Benefit Currency)",
    WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD.name: "Debit card fund usage (Benefit Currency)",
    WalletReportConfigColumnTypes.TOTAL_FUNDS_FOR_TAX_HANDLING.name: "Total funds for tax handling",
    WalletReportConfigColumnTypes.REIMBURSEMENT_TYPE.name: "Reimbursement Type",
    WalletReportConfigColumnTypes.COUNTRY.name: "Country",
    WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION.name: "Debit card funds awaiting substantiation",
    WalletReportConfigColumnTypes.PRIOR_PROGRAM_TO_DATE.name: "Prior Program to-date (Benefit Currency)",
    WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE.name: "Total Program to-date (Benefit Currency)",
    WalletReportConfigColumnTypes.TAXATION.name: "Taxation",
    WalletReportConfigColumnTypes.PAYROLL_DEPT.name: "Payroll Dept",
    WalletReportConfigColumnTypes.LINE_OF_BUSINESS.name: "Line of Business",
    WalletReportConfigColumnTypes.DIRECT_PAYMENT_FUND_USAGE.name: "Direct Payment Fund Usage",
    WalletReportConfigColumnTypes.EXPENSE_YEAR.name: "Expense Year",
}
ELIGIBILITY_SERVICE_COLS = [
    WalletReportConfigColumnTypes.FIRST_NAME.name,
    WalletReportConfigColumnTypes.LAST_NAME.name,
    WalletReportConfigColumnTypes.EMPLOYEE_ID.name,
    WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID.name,
    WalletReportConfigColumnTypes.DATE_OF_BIRTH.name,
    WalletReportConfigColumnTypes.LINE_OF_BUSINESS.name,
    WalletReportConfigColumnTypes.PAYROLL_DEPT.name,
]

# Columns included in every report. Does not need to be added in the report config.
DEFAULT_COLUMNS = {WalletReportConfigColumnTypes.EXPENSE_YEAR.name}


class AuditColumns:
    ALEGEUS_ID = "ALEGEUS_ID"
    AMOUNT = "AMOUNT"
    CLIENT_EMPLOYEE_ID = "CLIENT_EMPLOYEE_ID"
    COUNTRY = "COUNTRY"
    CREATED_DATE = "CREATED_DATE"
    LAST_CENSUS_FILE_BEFORE_DELETED = "LAST_CENSUS_FILE_BEFORE_DELETED"
    ORGANIZATION_EMPLOYEE_FIRST_NAME = "ORGANIZATION_EMPLOYEE_FIRST_NAME"
    ORGANIZATION_EMPLOYEE_LAST_NAME = "ORGANIZATION_EMPLOYEE_LAST_NAME"
    ORGANIZATION_ID = "ORGANIZATION_ID"
    ORGANIZATION_NAME = "ORGANIZATION_NAME"
    PROGRAM = "PROGRAM"
    REIMBURSEMENT_ID = "REIMBURSEMENT_ID"
    REIMBURSEMENT_METHOD = "REIMBURSEMENT_METHOD"
    SERVICE_START_DATE = "SERVICE_START_DATE"
    STATE = "STATE"
    TAXATION_STATUS = "TAXATION_STATUS"
    TRANSACTION_TYPE = "TRANSACTION_TYPE"
    WALLET_ID = "WALLET_ID"


AUDIT_COLUMN_NAMES = {
    AuditColumns.REIMBURSEMENT_ID: "Reimbursement ID",
    AuditColumns.TRANSACTION_TYPE: "Transaction Type",
    AuditColumns.ORGANIZATION_NAME: "Organization Name",
    AuditColumns.ORGANIZATION_ID: "Organization ID",
    AuditColumns.WALLET_ID: "Wallet ID",
    AuditColumns.CLIENT_EMPLOYEE_ID: "Client Employee ID",
    AuditColumns.CREATED_DATE: "Created Date",
    AuditColumns.LAST_CENSUS_FILE_BEFORE_DELETED: "Last Census File Before Deleted",
    AuditColumns.AMOUNT: "Amount",
    AuditColumns.STATE: "State",
    AuditColumns.REIMBURSEMENT_METHOD: "Reimbursement Method",
    AuditColumns.ALEGEUS_ID: "Alegeus ID",
    AuditColumns.ORGANIZATION_EMPLOYEE_FIRST_NAME: "Organization Employee First Name",
    AuditColumns.ORGANIZATION_EMPLOYEE_LAST_NAME: "Organization Employee Last Name",
    AuditColumns.TAXATION_STATUS: "Taxation Status",
    AuditColumns.SERVICE_START_DATE: "Service Start Date",
    AuditColumns.PROGRAM: "Program",
    AuditColumns.COUNTRY: "Country",
}

REIMBURSEMENT_AUDIT_REPORT_COLUMN_NAMES = {
    AuditColumns.ORGANIZATION_NAME: "Organization Name",
    AuditColumns.ORGANIZATION_ID: "Organization ID",
    AuditColumns.AMOUNT: "Amount",
    AuditColumns.REIMBURSEMENT_METHOD: "Reimbursement Method",
    AuditColumns.ALEGEUS_ID: "Alegeus ID",
    AuditColumns.ORGANIZATION_EMPLOYEE_FIRST_NAME: "Organization Employee First Name",
    AuditColumns.ORGANIZATION_EMPLOYEE_LAST_NAME: "Organization Employee Last Name",
    AuditColumns.SERVICE_START_DATE: "Service Start Date",
}


class TransactionalReportColumns:
    EMPLOYEE_ID = "EMPLOYEE_ID"
    FIRST_NAME = "FIRST_NAME"
    LAST_NAME = "LAST_NAME"
    DATE_OF_TRANSACTION = "DATE_OF_TRANSACTION"
    TRANSACTION_AMOUNT = "TRANSACTION_AMOUNT"


TRANSACTIONAL_REPORT_COLUMN_NAMES = {
    TransactionalReportColumns.EMPLOYEE_ID: "Employee ID",
    TransactionalReportColumns.FIRST_NAME: "First Name",
    TransactionalReportColumns.LAST_NAME: "Last Name",
    TransactionalReportColumns.DATE_OF_TRANSACTION: "Date of Transaction",
    TransactionalReportColumns.TRANSACTION_AMOUNT: "Transaction Amount",
}


class WalletReportConfigFilterType(enum.Enum):
    PRIMARY_EXPENSE_TYPE = "PRIMARY_EXPENSE_TYPE"
    COUNTRY = "COUNTRY"


class WalletReportConfigFilterCountry(enum.Enum):
    US = "US"
    UK = "UK"
    CA = "CA"
    OTHERS = "OTHERS"
