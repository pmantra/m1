from __future__ import annotations

import enum
import os
from pathlib import Path

from common.constants import Environment
from wallet.models.constants import ReimbursementRequestState

MAVEN_ADDRESS = {
    "address_1": "160 Varick St",
    "address_2": "6th Floor",
    "city": "New York",
    "state": "NY",
    "zip": "10013",
    "country": "US",
}


class EdiFileType(str, enum.Enum):
    IH = "IH"


class EdiTemplateName(str, enum.Enum):
    IMPORT = "Maven_Conversion_Import"
    RESULT = "Maven_Conversion_Results"
    EXPORT = "Maven_Conversion_Export"
    IMPORT_FOREIGN_IB = "Maven_Foreign_IB_Import"
    RESULT_FOREIGN_IB = "Maven_Foreign_IB_Results"
    EXPORT_FOREIGN_IB = "Maven_Foreign_IB_Export"


class FTPBucket(str, enum.Enum):
    QA2 = "12a2aff2-c2c7-2786-818c-dd6b23d3ae0b"
    PROD = "c1981798-6179-c28b-a026-2f1f1c1db094"


# Shared
ALEGEUS_EDI_BUCKET = os.environ.get("ALEGEUS_EDI_BUCKET")

# QA
ALEGEUS_API_CLIENT_ID = os.environ.get("ALEGEUS_API_CLIENT_ID")
ALEGEUS_API_SECRET = os.environ.get("ALEGEUS_API_SECRET")
ALEGEUS_API_USERNAME = os.environ.get("ALEGEUS_API_USERNAME")
ALEGEUS_API_PASSWORD = os.environ.get("ALEGEUS_API_PASSWORD")
ALEGEUS_BETA_TPAID = os.environ.get("ALEGEUS_TPAID")
ALEGEUS_TOKEN_URL = "https://access.beta.wealthcareadmin.com/access/connect/token"
ALEGEUS_EDI_BETA_PW = os.environ.get("ALEGEUS_EDI_PW")
ALEGEUS_BETA_WCA_URL = "https://www.mbibeta.com/MBIWebServicesREST"
ALEGEUS_BETA_WCP_URL = "https://beta.m.wealthcareadmin.com/ServiceProvider/services"
ALEGEUS_BETA_DEBIT_CARD_STOCK_ID = "M1004"
ALEGEUS_BETA_PAYROLL_ACCOUNT_NAME = "Import Bank Account"

# PROD
ALEGEUS_CONFIG_DIR = Path("/alegeus")
ALEGEUS_PROD_API_CLIENT_ID = os.environ.get("ALEGEUS_PROD_API_CLIENT_ID")
ALEGEUS_PROD_USER_ID = os.environ.get("ALEGEUS_PROD_USER_ID")
ALEGEUS_PROD_TPAID = os.environ.get("ALEGEUS_PROD_TPAID")
ALEGEUS_CERT_DIR = Path("/alegeus-certs")
ALEGEUS_CERT = ALEGEUS_CERT_DIR / "alegeus-client.crt"
ALEGEUS_PRIVATE_KEY = ALEGEUS_CERT_DIR / "alegeus-private-key.pem"
ALEGEUS_PROD_TOKEN_URL = "https://access.wealthcareadmin.com/access/connect/token"
ALEGEUS_PROD_WCA_URL = "https://www.mbiwebservices.com/MBIWebServicesRest"
ALEGEUS_PROD_WCP_URL = "https://m.wealthcareadmin.com/ServiceProvider/services"

ALEGEUS_EDI_PW = os.environ.get("ALEGEUS_PROD_EDI_PW")
ALEGEUS_FTP_USERNAME = os.environ.get("ALEGEUS_FTP_USERNAME")
ALEGEUS_FTP_HOST = os.environ.get("ALEGEUS_FTP_HOST")
ALEGEUS_FTP_PASSWORD = os.environ.get("ALEGEUS_FTP_PASSWORD")
ALEGEUS_PROD_DEBIT_CARD_STOCK_ID = "39186"
ALEGEUS_PROD_PAYROLL_ACCOUNT_NAME = "Payroll Client"

ALEGEUS_TPAID = (
    ALEGEUS_PROD_TPAID
    if Environment.current() == Environment.PRODUCTION
    else ALEGEUS_BETA_TPAID
)

ALEGEUS_WCA_URL = (
    ALEGEUS_PROD_WCA_URL
    if Environment.current() == Environment.PRODUCTION
    else ALEGEUS_BETA_WCA_URL
)
ALEGEUS_WCP_URL = (
    ALEGEUS_PROD_WCP_URL
    if Environment.current() == Environment.PRODUCTION
    else ALEGEUS_BETA_WCP_URL
)

ALEGEUS_PASSWORD_EDI = (
    ALEGEUS_EDI_PW
    if Environment.current() == Environment.PRODUCTION
    else ALEGEUS_EDI_BETA_PW
)

ALEGEUS_DEBIT_CARD_STOCK_ID = (
    ALEGEUS_PROD_DEBIT_CARD_STOCK_ID
    if Environment.current() == Environment.PRODUCTION
    else ALEGEUS_BETA_DEBIT_CARD_STOCK_ID
)

ALEGEUS_PAYROLL_ACCOUNT_NAME = (
    ALEGEUS_PROD_PAYROLL_ACCOUNT_NAME
    if Environment.current() == Environment.PRODUCTION
    else ALEGEUS_BETA_PAYROLL_ACCOUNT_NAME
)

# Reimbursement request state constants
APPROVED_REQUEST_STATES = frozenset(
    {
        ReimbursementRequestState.APPROVED,
        ReimbursementRequestState.REIMBURSED,
        ReimbursementRequestState.NEEDS_RECEIPT,
        ReimbursementRequestState.RECEIPT_SUBMITTED,
        ReimbursementRequestState.INSUFFICIENT_RECEIPT,
        ReimbursementRequestState.INELIGIBLE_EXPENSE,
        ReimbursementRequestState.RESOLVED,
        ReimbursementRequestState.REFUNDED,
    }
)

# Currently supported values for the configuration of reimbursement_organization_settings_allowed_category.currency_code
SUPPORTED_BENEFIT_CURRENCIES = frozenset(
    {"USD", "AUD", "BRL", "CAD", "CHF", "EUR", "GBP", "INR", "NZD"}
)

# Will be used to map currency code to the locale
# This can be dynamic in the future to support local currency != benefit currency
CURRENCY_TO_LOCALE_MAP: dict = {
    "USD": "en_US",
    "AUD": "en_AU",
    "BRL": "pt_BR",
    "CAD": "en_CA",
    "CHF": "en_CH",
    "EUR": "lb_LU",  # Luxembourg is our only EUR client for now, BEX-4672 will make this dynamic
    "GBP": "en_GB",
    "INR": "en_IN",
    "NZD": "en_NZ",
}

NUM_CREDITS_PER_CYCLE = 12

# This is used to calculate a dollar value of cycle-based plans. It's intended
# for putting a soft dollar cap on reimbursements against those plans. Do not
# use it as an exact cycle-to-dollars equivalent.
USD_DOLLARS_PER_CYCLE = 40000

UNLIMITED_FUNDING_USD_CENTS = 15_000_000_00

ORGS_WITH_LONG_QUESTIONNAIRES = frozenset(
    {
        30,  # Zynga_Inc
        62,  # SoFi
        83,  # Avalon Bay_Communities
        169,  # Huntington_Ingalls_Industries
        175,  # ValueAct_Capital
        182,  # Synnex
        184,  # Golden_Hippo_Group_LLC
        187,  # Centerbridge Partners
        215,  # Redesign Health
        216,  # LeapYear
        236,  # Gunderson_Dettmer
        302,  # Abry
        343,  # AEA Investors
        347,  # Take-Two US
        380,  # Willkie Farr & Gallagher LLP
        413,  # Hubbell
        418,  # ECS Federal
        421,  # Apex Systems
        422,  # ASGN
        423,  # Slalom Consulting - Medical Plan
        424,  # Creative Circle
        432,  # CyberCoders
        438,  # ICF International Inc.
        441,  # IPG
        496,  # The Madison Square Garden Company - Aetna Enrolled
        499,  # Baker and Hostetler, LLP - Texas, Post-Tax
        500,  # Baker and Hostetler, LLP - Texas, Pre-Tax
        501,  # Baker and Hostetler, LLP - Non-Texas Post-Tax
        502,  # Baker and Hostetler, LLP - Non-Texas, Pre-Tax
        543,  # 2U
        553,  # The Madison Square Garden Company - Union
        604,  # Crestview Advisors, LLC
        627,  # Lendlease - Medical Plan Enrolled
        645,  # Holder Construction (currently no active Wallets)
        676,  # PSG Equity
        680,  # Selendy Gay Elsberg PLLC
        683,  # Coatue Management, L.L.C.
        711,  # Sacramento Kings
        754,  # Silver Lake
        755,  # PAISBOA
        812,  # Miller Brothers’ Inc (currently no active Wallets)
    }
)

ALEGEUS_SYNCH_IN_CATEGORY_SETTINGS_JOB = "alegeus-synch-in-category-settings-job"

# Wallet Historical Spend

INTERNAL_TRUST_WHS_URL = os.environ.get("WHS_BASE_URL")
WHS_ADJUSTMENT_TOPIC = "wallet-spend-adjustment-notifications"
HISTORICAL_SPEND_LABEL = "Balance adjustment for prior benefit usage"
HISTORICAL_WALLET_FEATURE_FLAG = "enable-wallet-historical-spend-wallet-qualification"
WHS_LEDGER_SEARCH_BATCH_SIZE = int(os.environ.get("WHS_LEDGER_SEARCH_BATCH_SIZE", 20))
WHS_LEDGER_SEARCH_TIMEOUT_SECONDS = int(
    os.environ.get("WHS_LEDGER_SEARCH_TIMEOUT_SECONDS", 20)
)


class HistoricalSpendRuleResults(str, enum.Enum):
    ELIGIBLE = "Eligible"
    MAVEN_ERROR = "Maven Error"
    AWAITING_TRANSITION = "Awaiting Transition"

    def __str__(self) -> str:
        return str(self.value)


INTERNAL_TRUST_DOCUMENT_MAPPER_URL = os.environ.get("DOCUMENT_MAPPER_BASE_URL")

# payment gateway
INTERNAL_TRUST_PAYMENT_GATEWAY_URL = os.environ.get("BILLING_URL")
