import enum
import os
import re

from common.constants import Environment

# ======= Feature flags =======
ENABLE_UNLIMITED_BENEFITS_FOR_SMP = "unlimited-benefits-smp"

# ======= SMP Related Constants Starts =======
SMP_HOST = "ftp.smppharmacy.com"
SMP_FTP_USERNAME = os.environ.get("SMP_FTP_USERNAME")
SMP_FTP_PASSWORD = os.environ.get("SMP_FTP_PASSWORD")
SMP_ELIGIBILITY_FILE_PREFIX = "Maven_Custom_Rx_Eligibility"
SMP_RECONCILIATION_FILE_PREFIX = "MavenGold_StripePayments"
SMP_SCHEDULED_FILE_PREFIX = "Maven_Rx_Scheduled"
SMP_SHIPPED_FILE_PREFIX = "Maven_Rx_Shipped"
SMP_CANCELED_FILE_PREFIX = "Maven_Rx_Canceled"
SMP_REIMBURSEMENT_FILE_PREFIX = "Maven_Rx_Reimbursement"
SMP_INGEST_PROD_FOLDER_NAME = "Maven/FromSMP"
SMP_INGEST_TEST_FOLDER_NAME = "Maven/FromSMPTest"
SMP_PROD_FOLDER_NAME = "Maven/ToSMP"
SMP_TEST_FOLDER_NAME = "Maven/ToSMPTest"

SMP_FOLDER_NAME = (
    SMP_PROD_FOLDER_NAME
    if Environment.current() == Environment.PRODUCTION
    else SMP_TEST_FOLDER_NAME
)

SMP_INGEST_FOLDER_NAME = (
    SMP_INGEST_PROD_FOLDER_NAME
    if Environment.current() == Environment.PRODUCTION
    else SMP_INGEST_TEST_FOLDER_NAME
)

SMP_NCPDP_NUMBER = "NCPDP Number"
SMP_FIRST_NAME = "First Name"
SMP_LAST_NAME = "Last Name"
SMP_MAVEN_ID = "Maven Benefit ID"
SMP_MAVEN_USER_BENEFIT_ID = "User Benefit ID"
SMP_NDC_NUMBER = "NDC#"
SMP_DRUG_NAME = "Drug Name"
SMP_DRUG_DESCRIPTION = "Drug Description"
SMP_RX_RECEIVED_DATE = "Rx Received Date"
SMP_AMOUNT_OWED = "Amount Owed to SMP"
SMP_AMOUNT_PAID = "Amount Paid"
SMP_RX_ORDER_ID = "Order Number"
SMP_RX_FILLED_DATE = "Filled Date"
SMP_UNIQUE_IDENTIFIER = "Unique Identifier"
SMP_SCHEDULED_SHIP_DATE = "Scheduled Ship Date"
SMP_ACTUAL_SHIP_DATE = "Actual Ship Date"
SMP_RX_ADJUSTED = "Rx Adjusted"
SMP_RX_CANCELED_DATE = "Rx Canceled Date"
SMP_FERTILITY_CLINIC_1 = "SMP1-5710365"
SMP_FERTILITY_CLINIC_2 = "SMP2-1054573"
SMP_FERTILITY_CLINIC_4 = "SMP4-0539809"
SMP_FERTILITY_CLINIC_5 = "SMP5-2123242"

SCHEDULED_FILE_TYPE = "scheduled"
SHIPPED_FILE_TYPE = "shipped"
CANCELLED_FILE_TYPE = "cancelled"
REIMBURSEMENT_FILE_TYPE = "reimbursement"

SMP_RECONCILIATION_GET_DATA_TIME = "smp_reconciliation_get_data_exec_time"
SMP_RECONCILIATION_GET_DATA_FAILURE = "smp_reconciliation_get_data.error.count"

SMP_BUCKET_NAME = "SMP_BUCKET_NAME"

RX_NCPDP_ID_TO_FERTILITY_CLINIC_NAME = {
    "5710365": SMP_FERTILITY_CLINIC_1,
    "1054573": SMP_FERTILITY_CLINIC_2,
    "0539809": SMP_FERTILITY_CLINIC_4,
    "2123242": SMP_FERTILITY_CLINIC_5,
}

RX_GP_HCPCS_CODE = "S0126"

SMP_GCP_BUCKET_NAME = os.environ.get("SMP_BUCKET_NAME", "")
QUATRIX_OUTBOUND_BUCKET_NAME = os.environ.get("QUATRIX_OUTBOUND_BUCKET", "")
GCP_SMP_ELIGIBILITY_PATH = "Eligibility"
GCP_SMP_RECONCILIATION_PATH = "MavenGoldStripePayments"
GCP_SMP_INCOMING_PATH = "IncomingSMPFiles"

QUATRIX_OUTBOUND_BUCKET = (
    QUATRIX_OUTBOUND_BUCKET_NAME
    if Environment.current() == Environment.PRODUCTION
    else SMP_GCP_BUCKET_NAME
)

GCP_QUATRIX_ELIGIBILITY_PATH = "SMP_MavenGoldEligibility"
GCP_QUATRIX_RECONCILIATION_PATH = "SMP_MavenGoldStripePayments"
GCP_QUATRIX_ACKNOWLEDGMENT_PATH = "SMP_MavenAcknowledgment"
ENABLE_SMP_GCS_BUCKET_PROCESSING = "enable-smp-gcs-bucket-processing"


class SMPMemberType(enum.Enum):
    GOLD = "Maven Gold"
    GOLD_X = "Maven Gold X"
    GOLD_X_NO_HEALTH_PLAN = "Maven Gold X - No Health Plan"
    GOLD_REIMBURSEMENT = "Maven Gold Reimbursement"


# ======= SMP Related Constants Ends ==========

# ======= ESI Related Constants Starts =======
from pathlib import Path

current_dir = Path(__file__).resolve().parent

DEFAULT_SCHEMA_PATH = f"{current_dir}/tasks/esi_parser/esi_schema/esi_schema_v3.8.csv"
ESI_CLASS_NAME = "ESIRecord"
ESI_OUTBOUND_DIR = "From_ESI"
ESI_OUTBOUND_FILENAME_PATTERN = re.compile(r"^MAVN_RxAccum_(\d{8})_(\d{6})\.pgp")
ESI_BACKUP_FILENAME_PATTERN = re.compile(r"^raw/MAVN_RxAccum_(\d{8})_(\d{6})\.pgp")
ESI_DATE_OF_SERVICE_PATTERN = re.compile(r"^\d{8}$")
ESI_INGESTION_FAILURE = "esi_ingestion.error.count"
ESI_INGESTION_SUCCESS = "esi_ingestion.success.count"
ESI_INGESTION_EXECUTION_TIME = "esi_ingestion_exec_time"
ESI_PARSER_EXECUTION_TIME = "esi_parser_exec_time"
ESI_PARSER_FAILURE = "esi_parser.error.count"
ESI_PARSER_SUCCESS = "esi_parser.success.count"
ESI_PARSER_DR_RECORD_REJECTION = "esi_parser_dr_rejection.count"
ESI_PARSER_RECORD_CONVERTED = "esi_parser_record_converted.count"
ESI_PARSER_RECORD_SAVED = "esi_parser_record_saved.count"
ESI_INGESTION_SECRET = "ESI_INGESTION_SECRET"
ESI_DECRYPTION_SECRET = "ESI_DECRYPTION_SECRET"
ESI_BUCKET_NAME = "ESI_BUCKET_NAME"
# Reference from ESI CDH Implementation Guide NCPDP 1700 V3.8
ESI_REJECTION_ERROR_CODE_TO_REASON_MAP = {
    "0F3": "Accumulator Mismatch",
    "006": "M/I Group ID",
    "009": "M/I Date Of Birth",
    "010": "M/I Patient Gender Code",
    "011": "M/I Patient Relationship Code",
    "015": "M/I Date of Service",
    "021": "M/I Accumulator Balance Qualifier",
    "023": "M/I Accumulator Applied Amount",
    "024": "N/I Accumulator Benefit Period Amount",
    "025": "M/I Accumulator Remaining Balance",
    "061": "M/I In Network Indicator",
    "090": "Communication Error",
    "070": "Peak Hour Error",
    "051": "Non Matched Group Number",
    "052": "Non Matched Cardholder ID",
    "053": "Non Matched Person Code",
    "062": "Patient / Cardholder ID Name Mismatch",
    "064": "Claim Submitted does not match Prior Authorization",
    "065": "Patient Is Not Covered",
    "066": "Patient Age Exceeds Maximum Age",
    "067": "Filled Before Coverage Effective",
    "068": "Filled After Coverage Expired",
    "069": "Filled After Coverage Terminated",
    "081": "Record Archived",
    "05F": "Not processed due to no change in Accumulator Amount",
    "0F4": "Accumulator balance count does not match (POS 966)",
}

# ======= ESI Related Constants Ends ==========
