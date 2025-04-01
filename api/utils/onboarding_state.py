import os

from maven import feature_flags

from authn.models.user import User
from models.enterprise import OnboardingState, UserOnboardingState
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def update_onboarding_state(user: User, destination_state: OnboardingState):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not user.onboarding_state:
        log.info(
            "User does not have an onboarding state set. Adding a new "
            "UserOnboardingState.",
            user_id=user.id,
        )
        user.onboarding_state = UserOnboardingState(user=user, state=destination_state)
        db.session.add(user.onboarding_state)
    log.info(
        "Setting user onboarding state.",
        user_id=user.id,
        destination_state=destination_state.value,
    )
    user.onboarding_state.state = destination_state

    if not feature_flags.bool_variation(
        flag_key="kill-switch-braze-api-requests",
        default=not bool(os.environ.get("TESTING")),
    ):
        log.debug(
            "Skipping send_onboarding_state_to_braze when `kill-switch-braze-api-requests` flag is disabled."
        )
    else:
        from braze.attributes import send_onboarding_state_to_braze

        send_onboarding_state_to_braze.delay(user.esp_id, destination_state)
