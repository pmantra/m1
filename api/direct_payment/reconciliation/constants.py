from common.constants import Environment

CLINIC_RECONCILIATION_FILE_PREFIX = "Reconciliation_"
CLINIC_RECONCILIATION_REPORT_GENERATION_TIME_METRIC_NAME = (
    "clinic_reconciliation_report_generation_time"
)
CLINIC_RECONCILIATION_REPORT_GENERATION_ERROR_COUNT_METRIC_NAME = (
    "clinic_reconciliation_report_generation.error.count"
)

# Clinic reconciliation report field names
PATIENT_FIRST_NAME_FIELD_NAME = "Patient first name"
PATIENT_LAST_NAME_FIELD_NAME = "Patient last name"
PATIENT_DOB_FIELD_NAME = "Patient DOB"
PROCEDURE_NAME_FIELD_NAME = "Procedure name"
CLINIC_NAME_FIELD_NAME = "Clinic name"
CLINIC_LOCATION_NAME_FIELD_NAME = "Clinic location name"
UNIQUE_STRIPE_TX_ID_FIELD_NAME = "Unique Stripe Tx ID"
STRIPE_PAYOUT_ID_FIELD_NAME = "Stripe Payout ID"
PROCEDURE_START_DATE_FIELD_NAME = "Procedure Start Date"
PROCEDURE_END_DATE_FIELD_NAME = "Procedure End Date"
BILL_AMOUNT_FIELD_NAME = "Billed Amount"
PAID_AMOUNT_FIELD_NAME = "Paid Amount"

REPORT_FIELDS = [
    PATIENT_FIRST_NAME_FIELD_NAME,
    PATIENT_LAST_NAME_FIELD_NAME,
    PATIENT_DOB_FIELD_NAME,
    PROCEDURE_NAME_FIELD_NAME,
    CLINIC_NAME_FIELD_NAME,
    CLINIC_LOCATION_NAME_FIELD_NAME,
    UNIQUE_STRIPE_TX_ID_FIELD_NAME,
    STRIPE_PAYOUT_ID_FIELD_NAME,
    PROCEDURE_START_DATE_FIELD_NAME,
    PROCEDURE_END_DATE_FIELD_NAME,
    BILL_AMOUNT_FIELD_NAME,
    PAID_AMOUNT_FIELD_NAME,
]

# Clinic group names
CCRM_CLINIC_GROUP_NAME = "CCRM"
COLUMBIA_CLINIC_GROUP_NAME = "Columbia"
NYU_LANGONE_CLINIC_GROUP_NAME = "NYU Langone"
US_FERTILITY_CLINIC_GROUP_NAME = "US Fertility"

# Clinic names
ALL_REPORT_CLINIC_NAMES = [
    CCRM_CLINIC_GROUP_NAME,
    COLUMBIA_CLINIC_GROUP_NAME,
    NYU_LANGONE_CLINIC_GROUP_NAME,
]

# Others
TREATMENT_PROCEDURE_SOURCE_TYPE = "TreatmentProcedure"
PAYMENT_REFUND_SOURCE_TYPE = "payment_refund"

# QA
QA_CCRM_CLINIC_NAMES = ["Super Awesome Clinic"]
QA_US_FERTILITY_CLINIC_NAMES = ["Super Awesome Clinic"]
QA_NYU_LANGONE_CLINIC_NAMES = ["Super Awesome Clinic"]
QA_COLUMBIA_CLINIC_NAMES = ["Super Awesome Clinic"]

# PROD
PROD_CCRM_CLINIC_NAMES = ["CCRM"]
PROD_US_FERTILITY_CLINIC_NAMES = [
    "Center of Reproductive Medicine",
    "Fertility Centers of Illinois",
    "Georgia Reproductive Specialists",
    "IVF Florida Reproductive Associates",
    "Reproductive Science Center of the San Francisco Bay Area",
    "SGF Colorado PLLC",
    "SGF LLC",
    "SGF North Carolina",
    "SGF Orlando, LLC",
    "SGF Tampa Bay, LLC",
    "Shady Grove Fertility Center of Pennsylvania, PLL",
    "Virginia Fertility Associates, SGF Richmond d/b/a SGF Jones Institute",
]
PROD_NYU_LANGONE_CLINIC_NAMES = ["NYU Langone Fertility Center"]
PROD_COLUMBIA_CLINIC_NAMES = ["Columbia University"]

CCRM_CLINIC_NAMES = (
    PROD_CCRM_CLINIC_NAMES
    if Environment.current() == Environment.PRODUCTION
    else QA_CCRM_CLINIC_NAMES
)

US_FERTILITY_CLINIC_NAMES = (
    PROD_US_FERTILITY_CLINIC_NAMES
    if Environment.current() == Environment.PRODUCTION
    else QA_US_FERTILITY_CLINIC_NAMES
)

NYU_LANGONE_CLINIC_NAMES = (
    PROD_NYU_LANGONE_CLINIC_NAMES
    if Environment.current() == Environment.PRODUCTION
    else QA_NYU_LANGONE_CLINIC_NAMES
)

COLUMBIA_CLINIC_NAMES = (
    PROD_COLUMBIA_CLINIC_NAMES
    if Environment.current() == Environment.PRODUCTION
    else QA_COLUMBIA_CLINIC_NAMES
)
