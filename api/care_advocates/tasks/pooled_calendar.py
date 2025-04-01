import datetime

from authn.models.user import User
from care_advocates.services.care_advocate import CareAdvocateService
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job
def log_7_day_availability_in_pooled_calendar(
    care_advocate_ids: list[int], user_id: int
) -> None:
    user = User.query.get(user_id)
    log.info(
        "Starting to build pooled availability for next 7 days",
        ca_ids=care_advocate_ids,
        user_id=user.id,
    )

    signed_up_at = user.created_at

    # Build pooled availability for the next 7 days starting from account creation date
    # We don't log explicitly in this method, the _log_time_coverage call within build_pooled_availability
    # will log the 7 day availability and all necessary metadata
    CareAdvocateService().build_pooled_availability(
        ca_ids=care_advocate_ids,
        start_at=signed_up_at,
        end_at=signed_up_at + datetime.timedelta(days=7),
        user=user,
    )
