import enum
import os
import re

from payer_accumulator.common import PayerName

DATA_ELEMENT_SEPARATOR = "*"
COMPOSITE_FIELD_SEPARATOR = "<"
SUB_ELEMENT_SEPARATOR = ":"
SEGMENT_TERMINATOR = "~"
REPETITION_SEPARATOR = "^"
NEW_LINE_SEPARATOR = "\n"
BLANK_SPACE = " "
INSURED_OR_SUBSCRIBER_ENTITY_ID = "IL"

AETNA_277_FILENAME_PATTERN = re.compile(r"^277-AETNA60054-(\d{8})(\d{8})-(\d{3})\.277$")
AETNA_277_FILENAME_DATE_INDEX = 1
AETNA_277CA_FILENAME_PATTERN = re.compile(r"^277-(\d{8})(\d{10})\.277ebr$")
AETNA_277CA_FILENAME_DATE_INDEX = 1
AVAILITY_SFTP_SECRET = os.environ.get("AVAILITY_SFTP_SECRET")
AVAILITY_PORT_NUMBER = 9922
AVAILITY_OUTBOUND_DIR = "SendFiles"
AVAILITY_INGESTION_DIR = "ReceiveFiles"
AETNA_INGESTION_FAILURE = "aetna_ingestion.error.count"


class SchemaType(enum.Enum):
    EDI_837 = "837"
    EDI_835 = "835"
    EDI_276 = "276"
    EDI_277 = "277"
    EDI_277CA = "277CA"


class Segments(enum.Enum):
    INTERCHANGE_CONTROL_HEADER = "ISA"
    TRANSACTION_SET_HEADER = "ST"
    INDIVIDUAL_OR_ORGANIZATIONAL_NAME = "NM1"
    STATUS_INFORMATION = "STC"
    TRACE = "TRN"
    TRANSACTION_SET_TRAILER = "SE"


class AcceptedClaimStatusCategoryCodes(enum.Enum):
    CLAIM_FINALIZED = "F0"  # Finalized
    PAYMENT_MADE = "F1"  # Finalized/Payment
    FINALIZED_REVISED = "F3"  # Finalized/Revised
    FORWARDED = "F3F"  # Finalized/Forwarded
    NOT_FORWARDED = "F3N"  # Finalized/Not Forwarded
    ADJ_COMPLETE = "F4"  # Adjudication Complete


class RejectedClaimStatusCategoryCodes(enum.Enum):
    UNPROCESSABLE = "A3"  # Returned as unprocessable claim
    NOT_FOUND = "A4"  # Acknowledgement/Not Found
    MISSING_INFO = "A6"  # Rejected for Missing Information
    INVALID_INFO = "A7"  # Rejected for Invalid Information
    RELATIONAL_FIELD_ERR = "A8"  # Rejected for relational field in error
    DATA_UNPROCESSABLE = "DR03"  # Data reporting unprocessable claim
    DATA_NOT_FOUND = "DR04"  # Acknowledgement/Not Found (data reporting)
    DATA_MISSING_INFO = "DR05"  # Missing Information (data reporting)
    DATA_INVALID_INFO = "DR06"  # Invalid information (data reporting)
    DATA_RELATIONAL_ERR = "DR07"  # Relational field in error (data reporting)
    ERROR_RESPONSE = "E0"  # Response not possible - error on submitted request data
    SYSTEM_STATUS_ERR = "E1"  # Response not possible - System Status
    NOT_RESPONDING = "E2"  # Information Holder not responding
    RELATIONAL_ERR = "E3"  # Correction required - relational fields in error
    DATA_CORRECTION_REQ = "E4"  # Data correction required
    DENIAL = "F2"  # Finalized/Denial
    DATA_SEARCH_UNSUCCESSFUL = "D0"  # Data Search Unsuccessful


PAYERNAME_MAPPING = {
    PayerName.AETNA: dict(payer_name="AETNA COMMERCIAL", payer_identifier="60054")
}
