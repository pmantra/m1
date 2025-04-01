import os
from typing import Final

INTERNAL_TRUST_PAYMENT_GATEWAY_URL = os.environ.get("BILLING_URL")

# The error_types that the UI expects.
CONTACT_CARD_ISSUER = "CONTACT_CARD_ISSUER"
INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
OTHER_MAVEN = "OTHER_MAVEN"
PAYMENT_METHOD_HAS_EXPIRED = "PAYMENT_METHOD_HAS_EXPIRED"
REQUIRES_AUTHENTICATE_PAYMENT = "REQUIRES_AUTHENTICATE_PAYMENT"
UNKNOWN = "UNKNOWN"

# Mapping from stripe decline codes, and payment gateway errors to UI codes
# sourced from: https://www.notion.so/mavenclinic/Payment-transaction-detail-show-payment-error
DECLINE_CODE_MAPPING = {
    "authentication_required": REQUIRES_AUTHENTICATE_PAYMENT,
    "expired_card": PAYMENT_METHOD_HAS_EXPIRED,
    "insufficient_funds": INSUFFICIENT_FUNDS,
    "call_issuer": CONTACT_CARD_ISSUER,
    "card_not_supported": CONTACT_CARD_ISSUER,
    "card_velocity_exceeded": CONTACT_CARD_ISSUER,
    "do_not_honor": CONTACT_CARD_ISSUER,
    "do_not_try_again": CONTACT_CARD_ISSUER,
    "generic_decline": CONTACT_CARD_ISSUER,
    "invalid_account": CONTACT_CARD_ISSUER,
    "new_account_information_available": CONTACT_CARD_ISSUER,
    "no_action_taken": CONTACT_CARD_ISSUER,
    "not_permitted": CONTACT_CARD_ISSUER,
    "pickup_card": CONTACT_CARD_ISSUER,
    "restricted_card": CONTACT_CARD_ISSUER,
    "revocation_of_all_authorizations": CONTACT_CARD_ISSUER,
    "revocation_of_authorization": CONTACT_CARD_ISSUER,
    "security_violation": CONTACT_CARD_ISSUER,
    "service_not_allowed": CONTACT_CARD_ISSUER,
    "stop_payment_order": CONTACT_CARD_ISSUER,
    "transaction_not_allowed": CONTACT_CARD_ISSUER,
    "unknown": UNKNOWN,
    "other_maven": OTHER_MAVEN,
}

# sourced from https://gitlab.com/maven-clinic/services/payments/-/blob/main/src/payments/client/http/openapi.yml?ref_type=heads&plain=1#L230
GATEWAY_EXCEPTION_CODE_MAPPING = {
    400: "GeneralPaymentProcessorError",
    422: "ValidationErrorResponse",
    429: "RateLimitPaymentProcessorError",
    503: "ConnectionPaymentProcessorError",
}

DEFAULT_GATEWAY_ERROR_RESPONSE: Final[str] = "HTTPErrorResponse"

MEMBER_BILLING_OFFSET_DAYS: Final[int] = 7

CONFIGURE_BILLING_ABS_AUTO_PROCESS_MAX_AMOUNT: Final[
    str
] = "CONFIGURE_BILLING_ABS_AUTO_PROCESS_MAX_AMOUNT"

ENABLE_DELAYED_BILLING_FOR_INVOICED_EMPLOYERS: Final[
    str
] = "enable-delayed-billing-for-invoiced-employers"

# orgs that need special handling
ORG_ID_AMAZON = 2441
ORG_ID_OHIO = 2018

# TODO remove in Feb 2025
INVOICED_ORGS_PILOT = {ORG_ID_AMAZON, ORG_ID_OHIO}
