from tasks.helpers import get_user
from tasks.queues import job
from utils import braze, braze_events
from utils.log import logger

log = logger(__name__)


@job  # type: ignore
def update_health_profile_in_braze(user_id: int) -> None:
    user = get_user(user_id)
    if not user:
        log.warning("User id not found", user_id=user_id)
        return
    braze.update_health_profile(user)


@job  # type: ignore
def send_braze_fertility_status(user_id: int, status: str) -> None:
    user = get_user(user_id)
    braze_events.fertility_status(user=user, status=status)


@job  # type: ignore
def send_braze_prior_c_section_status(user_id: int, status: bool) -> None:
    user = get_user(user_id)
    braze_events.prior_c_section_status(user=user, status=status)


@job  # type: ignore
def send_braze_biological_sex(user_id: int, biological_sex: str) -> None:
    user = get_user(user_id)
    braze_events.biological_sex(user=user, biological_sex=biological_sex)
