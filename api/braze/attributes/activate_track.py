from authn.models.user import User
from tasks.helpers import get_user
from tasks.queues import job
from utils import braze
from utils.log import logger

log = logger(__name__)


@job(team_ns="enrollments", service_ns="tracks")
def activate_track(user_id: int) -> None:
    user: User = get_user(user_id=user_id)
    if not user:
        log.warning("User id not found", user_id=user_id)
        return None
    braze.activate_track(user=user)
    log.info("Braze activate track invoked", user_id=user_id)
