from models.enterprise import OnboardingState
from tasks.queues import job
from utils import braze
from utils.log import logger

log = logger(__name__)


@job(team_ns="enrollments", service_ns="tracks")
def send_onboarding_state_to_braze(
    esp_id: str, onboarding_state: OnboardingState
) -> None:
    try:
        braze.send_onboarding_state(esp_id, onboarding_state)
    except Exception as err:
        log.error("Error sending onboarding_state to Braze", err=err)
