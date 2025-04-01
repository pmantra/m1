from maven import feature_flags

from utils import launchdarkly


def marshmallow_experiment_enabled(
    flag_key: str, user_esp_id: str, user_email: str, default: bool
) -> bool:
    ctx = (
        launchdarkly.marshmallow_context(user_esp_id, user_email)
        if user_esp_id
        else None
    )
    return feature_flags.bool_variation(flag_key, ctx, default=default)
