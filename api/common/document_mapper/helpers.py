from difflib import SequenceMatcher

from maven import feature_flags

RECEIPT_VALIDATION_OPS_VIEW_FLAG = "receipt-validation-operations-view"
RECEIPT_VALIDATION_OPS_VIEW_INTERNAL_FLAG = (
    "receipt-validation-operations-view-internal"
)
FUZZY_MATCH_THRESHOLD = 80.0


def receipt_validation_ops_view_enabled(
    service_provider: str, member_facing: bool = True
) -> bool:
    """
    Helper function that determines if a service provider has been enabled for receipt validation via feature flag.
    Note this does approximate partial matching. We want to allow for typos and for the member inputting extra details
    in the service provider input, for example they may put 'CCRM New York' instead of just CCRM.
    """
    if member_facing:
        providers = feature_flags.str_variation(
            RECEIPT_VALIDATION_OPS_VIEW_FLAG, default=""
        ).split(",")
    else:
        providers = feature_flags.str_variation(
            RECEIPT_VALIDATION_OPS_VIEW_INTERNAL_FLAG, default=""
        ).split(",")

    return any(
        partial_ratio(p.strip(), service_provider) >= FUZZY_MATCH_THRESHOLD
        for p in providers
        if p
    )


def partial_ratio(s1: str, s2: str) -> float:
    s1, s2 = s1.strip(), s2.strip()
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    max_ratio = 0.0
    for i in range(len(s2) - len(s1) + 1):
        ratio = SequenceMatcher(None, s1, s2[i : i + len(s1)]).ratio()
        max_ratio = max(max_ratio, ratio)
    return max_ratio * 100
