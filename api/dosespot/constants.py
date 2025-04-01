import os

from utils.log import logger

log = logger(__name__)

"""
DoseSpot API V1 variables
"""
DOSESPOT_API_URL = os.environ.get(
    "DOSESPOT_API_URL", "https://my.staging.dosespot.com/webapi/"
)
DOSESPOT_GLOBAL_CLINIC_ID = os.environ.get("DOSESPOT_GLOBAL_CLINIC_ID", 123977)
DOSESPOT_GLOBAL_CLINIC_KEY = os.environ.get(
    "DOSESPOT_GLOBAL_CLINIC_KEY", "DG9UMXALAS7MNXC9MNK6EF6F96MCEF2A"
)
DOSESPOT_GLOBAL_CLINIC_USER_ID = os.environ.get("DOSESPOT_GLOBAL_CLINIC_USER_ID", 482)

"""
DoseSpot API V2 variables
"""
DOSESPOT_API_URL_V2 = os.environ.get(
    "DOSESPOT_API_URL_V2", "https://my.staging.dosespot.com/webapi/v2/"
)
DOSESPOT_GLOBAL_CLINIC_ID_V2 = os.environ.get("DOSESPOT_GLOBAL_CLINIC_ID_V2", 0)
DOSESPOT_GLOBAL_CLINIC_KEY_V2 = os.environ.get("DOSESPOT_GLOBAL_CLINIC_KEY_V2", "")
DOSESPOT_GLOBAL_CLINIC_USER_ID_V2 = os.environ.get(
    "DOSESPOT_GLOBAL_CLINIC_USER_ID_V2", 0
)
DOSESPOT_SUBSCRIPTION_KEY = os.environ.get("DOSESPOT_SUBSCRIPTION_KEY", "")

"""
Global variables
"""
DOSESPOT_SSO_URL = os.environ.get(
    "DOSESPOT_SSO_URL", "https://my.staging.dosespot.com/LoginSingleSignOn.aspx"
)

MAX_RETRIES = 3
RETRY_DELAY = 0.3


class DoseSpotActionTypes:
    request_provider_errors = "request_provider_errors"
    create_patient = "create_patient"
    get_patient_details_url = "get_patient_details_url"
    pharmacy_search = "pharmacy_search"
    validate_pharmacy = "validate_pharmacy"
    get_medication_list = "get_medication_list"
    add_patient_pharmacy = "add_patient_pharmacy"
