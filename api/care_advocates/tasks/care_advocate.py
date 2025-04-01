from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job
def check_care_advocates_for_3_day_availability(care_advocate_ids, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(
        "Checking potential CAs for 3 day availability",
        user_id=user_id,
        ca_ids=care_advocate_ids,
    )
    care_advocate_has_3_day_availability = (
        AssignableAdvocate.care_advocate_has_3_day_availability(care_advocate_ids)
    )

    if not care_advocate_has_3_day_availability:
        user = db.session.query(User).get(user_id)
        # dd monitor https://app.datadoghq.com/monitors/140804436
        log.warning(
            "None of the user's potential CAs have availability within 3 days.",
            user_id=user_id,
            track=[track.name for track in user.active_tracks],
            country=user.country and user.country.alpha_2,
            organization=user.organization and user.organization.name,
        )
        return
    log.info(
        "User's potential CAs have availability within 3 days.",
        user_id=user_id,
    )
    return
