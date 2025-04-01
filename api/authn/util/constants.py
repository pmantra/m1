USER_METRICS_PREFIX = "api.authn.resources.user"
SSO_METRICS_PREFIX = "api.authn.resources.sso"
API_MIGRATION_PREFIX = "authnapi.migration"

REFRESH_TOKEN_EXPIRE_AT_KEY = "refresh_token_expires_at"

SECONDS_SEVEN_DAYS = 604800

SECONDS_FIVE_MIN = 300

CLIENT_ERROR_MESSAGE = (
    "There was an error creating your account, "
    "please make sure you are using a secure password "
    "and that you don't already have an account registered with the same email address or username."
)

SERVER_ERROR_MESSAGE = (
    "There was an error creating your account, please try again. "
    "Contact the support team if the error persists."
)

ENABLE_MFA = "enable_mfa"

########### Launch Darkly ##############
UNIVERSAL_LOGIN_SIGN_IN_LAUNCH_DARKLY_KEY = "auth0-universal-login"
UNIVERSAL_LOGIN_SIGN_IN_LAUNCH_DARKLY_CONTEXT_NAME = "login"

COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY = "release-company-mfa-sync-lts"
COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME = "company-mfa"

SSO_HARD_CHECK_FF_KEY = "enable-sso-request-rejection"
SSO_SOFT_CHECK_FF_KEY = "enable-sso-user-data-cross-link-check"
SSO_USER_DATA_STORAGE = "id-p-user-data-storage"
########################################

################## SSO #################
OPTUM_WEB_CONNECTION_NAME = "Optum-Web"
OPTUM_MSO_CONNECTION_NAME = "Optum-MSP"

SSO_VALIDATION_METRICS_PREFIX = "authn.sso.validation"

ERROR_REASON_1_FOR_NEW_SSO_USER = "Found invalid record in user external identity based on auth0 user id for new sso user"
ERROR_REASON_2_FOR_NEW_SSO_USER = "Found invalid record in user external identity based on idp id and external user id for new sso user"
SUCCESS_CHECK_FOR_NEW_SSO_USER = "Data validation check pass for new sso user"

ERROR_REASON_1_FOR_EXISTING_SSO_USER = "Missing record in user_external_identity based on auth user id for existing sso user"
ERROR_REASON_2_FOR_EXISTING_SSO_USER = (
    "Maven user id mismatch with that in the access token for existing sso user"
)
ERROR_REASON_3_FOR_EXISTING_SSO_USER = "Data mismatch in user_external_identity based on idp id and external user id for existing sso user"
ERROR_REASON_4_FOR_EXISTING_SSO_USER = (
    "Data mismatch in SAML attributes for existing sso user"
)
SUCCESS_CHECK_FOR_EXISTING_SSO_USER = "Data validation check pass for existing sso user"

REJECT_DUE_TO_HARD_CHECK_FAIL = "Reject due to hard check failed"
########################################


########### Data Migration #############
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
########################################
