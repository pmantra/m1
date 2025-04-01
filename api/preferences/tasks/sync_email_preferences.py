from __future__ import annotations

import dataclasses
import datetime
from typing import List

from authn.domain.repository import UserRepository
from braze import client
from braze.client import constants
from common import stats
from preferences import models, service
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


user_repository = UserRepository()
preference_service = service.PreferenceService()
member_preferences_service = service.MemberPreferencesService()


log = logger(__name__)


DEFAULT_BATCH_SIZE = 1_000
OPTED_IN_EMAIL_COMMUNICATIONS = "opted_in_email_communications"
# this is the maximum number of results Braze will return in a single call to its endpoint
BRAZE_REQUEST_LIMIT = 500


@job(team_ns="enrollments", service_ns="member_profile")
def sync_member_email_preference_with_braze():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    This job updates member email preference daily with unsubscribed from braze.
    """
    log.info("Sync email opt-in preference with unsubscribed from braze.")

    opt_in_email_pref = preference_service.get_by_name(
        name=OPTED_IN_EMAIL_COMMUNICATIONS
    )
    if not opt_in_email_pref:
        log.error(
            "preference not found",
            name=OPTED_IN_EMAIL_COMMUNICATIONS,
        )
        return

    unsubscribe_updates: [UpdateDataRow] = get_rows_with_unsubscribe_email(  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        preference=opt_in_email_pref
    )
    update_preferences(unsubscribe_updates)


def get_rows_with_unsubscribe_email(
    preference: models.Preference,
) -> [UpdateDataRow]:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
    """
    Call the Braze API to get users who unsubscribed.
    Find the corresponding member_preference_id,
    Put data into array of UpdateDataRow for later usage.

    Braze API max limit to 500, may need call it multiple times
    """
    log.info("Calling Braze to find users who unsubscribed")
    offset = 0
    rows = []

    today = datetime.datetime.utcnow()
    yesterday = today - datetime.timedelta(1)

    braze_client = client.BrazeClient()

    while True:
        cur_batch = braze_client.get_unsubscribes(
            start_date=yesterday.date(),
            end_date=today.date(),
            offset=offset,
        )
        for email in cur_batch:
            # look up the user by email
            user = user_repository.get_by_email(email=email)
            if not user:
                log.warn("Could not find user by email", email=email)
                continue

            # If user does not have a MemberPreference for email comms,
            # create a MemberPreference and set the value to false
            existing_member_pref = member_preferences_service.get_by_preference_name(
                member_id=user.id,
                preference_name=preference.name,
            )
            if existing_member_pref:
                rows.append(
                    UpdateDataRow(
                        member_preference_id=existing_member_pref.id,
                        email=email,
                    )
                )

        if len(cur_batch) < constants.UNSUBSCRIBES_ENDPOINT_LIMIT:
            break
        else:
            offset += len(cur_batch)

    return rows


def update_preferences(update_rows: List[UpdateDataRow]) -> None:
    """
    update member_preference table
    @param update_rows: rows to be updated
    @return: None
    """
    metric_prefix = "api.tasks.preferences.sync_member_email_preference_with_braze"
    session = db.session().using_bind("default")

    for update_row in update_rows:
        try:
            session.execute(
                """UPDATE `member_preferences`
                    SET value=:value, modified_at=:modified_at
                WHERE id=:id
                """,
                {
                    "id": update_row.member_preference_id,
                    "value": "false",
                    "modified_at": datetime.datetime.utcnow(),
                },
            )
            log.info(
                "update row success",
                member_preferences_id=update_row.member_preference_id,
                email=update_row.email,
            )
            session.commit()
            stats.increment(
                metric_name=f"{metric_prefix}.transaction",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["status:complete"],
            )
        except Exception as e:
            db.session.rollback()
            log.exception(
                "Unhandled exception occurred while updating member_preference with braze unsubscribed email",
                exception=e,
                member_preference_id=update_row.member_preference_id,
                email=update_row.email,
            )
            stats.increment(
                metric_name=f"{metric_prefix}.transaction",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["status:unexpected_error"],
            )
            continue


@dataclasses.dataclass
class UpdateDataRow:
    __slots__ = ("member_preference_id", "email")

    member_preference_id: int
    email: str
