from __future__ import annotations

import datetime

from appointments.models.appointment import Appointment
from authn.models.user import User
from models.referrals import ReferralCode
from storage.connection import db
from tasks.helpers import get_user
from tasks.queues import job
from utils import braze, index_resources
from utils.log import logger
from utils.mail import send_message

log = logger(__name__)


@job(team_ns="enrollments")
def track_user_in_braze(user_id: int | str) -> None:
    user = get_user(user_id)
    if not user:
        log.warning("User id not found: %s", user_id)
        return
    braze.track_user(user)


@job(team_ns="enrollments")
def repopulate_braze(esp_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for esp_id in esp_ids:
        user = db.session.query(User).filter(User.esp_id == esp_id).one_or_none()
        if not user:
            log.warning(f"Could not find user with esp_id: {esp_id}")
            continue
        braze.track_user(user)


@job(team_ns="enrollments")
def find_users_to_tag(since_hours: int = 24) -> None:
    since = None
    if since_hours is not None:
        since = datetime.datetime.utcnow() - datetime.timedelta(hours=since_hours)

    now = datetime.datetime.utcnow()
    completed = db.session.query(Appointment).filter(
        (
            (Appointment.member_ended_at < now)
            | (Appointment.practitioner_ended_at < now)
        ),
        Appointment.cancelled_at == None,
    )
    if since:
        completed = completed.filter(Appointment.scheduled_end >= since)

    completed = completed.all()
    log.debug("Got %d appts completed since %s", len(completed), since)
    for appt in completed:
        if appt.member.is_enterprise:
            appt_purpose_tag_map = {
                "introduction": "has_completed_intro_appt",
                "birth_needs_assessment": "has_completed_intro_appt",
                "birth_planning": "has_completed_birth_planning_appt",
            }
            ent_event = appt_purpose_tag_map.get(appt.purpose)
            log.debug("Tagging enterprise appt completed event: %s", ent_event)
            if ent_event:
                braze.update_appointment_attrs(appt.member)


@job(team_ns="enrollments")
def check_expiring_codes():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    now = datetime.datetime.utcnow()
    p24 = now + datetime.timedelta(hours=24)

    expiring = (
        db.session.query(ReferralCode)
        .filter(ReferralCode.expires_at >= now, ReferralCode.expires_at <= p24)
        .all()
    )

    if expiring:
        log.debug(f"Got {len(expiring)} codes expiring in next 24h to alert on")

        alert_text = "Expiring codes in next 24 hours:\n" + "".join(
            f"{code}\n" for code in expiring
        )

        for email in [
            "tom@mavenclinic.com",
            "kalli@mavenclinic.com",
            "kaitlyn@mavenclinic.com",
        ]:
            send_message(
                email,
                f"Expiring Codes @ {now.date()}",
                text=alert_text,
                internal_alert=True,
            )
    else:
        log.debug("No expiring codes in next 24h to alert on")


@job
def index_resources_for_search():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    index_resources.run()
