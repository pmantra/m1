import os

from common.constants import Environment
from payer_accumulator.common import PayerName

ACCUMULATION_FILE_BUCKET = os.environ.get("PAYER_ACCUMULATOR_FILE_BUCKET", "")
ACCUMULATION_RESPONSE_BUCKET = os.environ.get("PAYER_ACCUMULATOR_RESPONSE_BUCKET", "")
LOCAL_FILE_BUCKET = "./payer_accumulator/sample_files/"

# data-sender constants
# TODO: deprecate data sender and use quatrix instead
DATA_SENDER_BUCKET = os.environ.get("DATA_SENDER_OUTBOUND_BUCKET", "")
CIGNA_FOLDER = "cigna_accumulation"
ESI_PROD_FOLDER = "esi_prod"
ESI_TEST_FOLDER = "esi_qa"

ESI_FOLDER = (
    ESI_PROD_FOLDER
    if Environment.current() == Environment.PRODUCTION
    else ESI_TEST_FOLDER
)
UHC_FOLDER = "uhc"
PGP_ENCRYPTION_PAYERS = {
    PayerName.ANTHEM,
}
QUATRIX_PAYERS = {
    PayerName.AETNA,
    PayerName.CREDENCE,
    PayerName.CIGNA_TRACK_1,
    PayerName.LUMINARE,
    PayerName.PREMERA,
    PayerName.SUREST,
}
PGP_ENCRYPTION_OUTBOUND_BUCKET = os.environ.get("PGP_ENCRYPTION_OUTBOUND_BUCKET", "")
QUATRIX_OUTBOUND_BUCKET = os.environ.get("QUATRIX_OUTBOUND_BUCKET", "")
AETNA_QUATRIX_FOLDER = "Availity_Accumulators"
ANTHEM_QUATRIX_FOLDER = "Anthem_Accumulator"
CREDENCE_QUATRIX_FOLDER = "Credence_Accumulator"
CIGNA_AMAZON_QUATRIX_FOLDER = "Cigna_Accumulator_Amazon"
CIGNA_GOLDMAN_QUATRIX_FOLDER = "Cigna_Accumulator_Goldman"
LUMINARE_PROD_FOLDER = "OhioHealth_Luminare_Accumulator_PROD"
LUMINARE_TEST_FOLDER = "OhioHealth_Luminare_Accumulator_QA"
LUMINARE_QUATRIX_FOLDER = (
    LUMINARE_PROD_FOLDER
    if Environment.current() == Environment.PRODUCTION
    else LUMINARE_TEST_FOLDER
)
PREMERA_QUATRIX_FOLDER = "Premera_Accumulator"
SUREST_QUATRIX_FOLDER = "Surest_Accumulator"
