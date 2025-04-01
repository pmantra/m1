from typing import Optional

from common.constants import Environment

# TODO: setup an account for GDPR deletion
GDPR_DELETION_INITIATOR_USER_ID_QA1 = 374732
GDPR_DELETION_INITIATOR_USER_ID_QA2 = 75977
GDPR_DELETION_INITIATOR_USER_ID_STAGING = None
GDPR_DELETION_INITIATOR_USER_ID_PROD = 402522


def get_gdpr_deletion_initiator_user_id() -> Optional[int]:
    current_env = Environment.current()

    if current_env == Environment.PRODUCTION:
        return GDPR_DELETION_INITIATOR_USER_ID_PROD
    if current_env == Environment.STAGING:
        return GDPR_DELETION_INITIATOR_USER_ID_STAGING
    if current_env == Environment.QA1:
        return GDPR_DELETION_INITIATOR_USER_ID_QA1
    if current_env == Environment.QA2:
        return GDPR_DELETION_INITIATOR_USER_ID_QA2
    return None


def get_env_name() -> str:
    current_env = Environment.current()

    if current_env == Environment.PRODUCTION:
        return "prod"
    if current_env == Environment.STAGING:
        return "staging"
    if current_env == Environment.QA1:
        return "qa1"
    if current_env == Environment.QA2:
        return "qa2"
    return ""
