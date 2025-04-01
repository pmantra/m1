from maven import feature_flags

from authn.models.user import User
from utils.launchdarkly import user_context


def can_show_questionnaire_by_appt_vertical(user: User) -> bool:
    if user is None:
        return False

    return feature_flags.bool_variation(
        "experiment-post-appointment-questionnaire-from-vertical",
        user_context(user),
        default=False,
    )
