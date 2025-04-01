import datetime

from models.zoom import UserWebinar, UserWebinarStatus, Webinar
from storage.connection import db
from tasks.queues import job
from utils import braze, braze_events, zoom
from utils.log import logger

log = logger(__name__)


@job
def add_new_upcoming_webinars():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    upcoming_webinars = zoom.get_upcoming_webinars()
    upcoming_webinar_ids = {w["id"] for w in upcoming_webinars}
    current_webinar_ids = {x[0] for x in db.session.query(Webinar.id).all()}

    webinars_to_remove = current_webinar_ids - upcoming_webinar_ids

    for webinar in upcoming_webinars:
        if int(webinar["id"]) not in current_webinar_ids:
            webinar = Webinar(
                id=webinar["id"],
                uuid=webinar["uuid"],
                duration=webinar["duration"],
                timezone=webinar["timezone"],
                topic=webinar["topic"],
                type=webinar["type"],
                agenda=webinar.get("agenda"),
                host_id=webinar["host_id"],
                start_time=datetime.datetime.strptime(
                    webinar["start_time"], "%Y-%m-%dT%H:%M:%SZ"
                ),
                created_at=datetime.datetime.strptime(
                    webinar["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                ),
            )
            db.session.add(webinar)

    for webinar in (
        db.session.query(Webinar).filter(Webinar.id.in_(webinars_to_remove)).all()
    ):
        db.session.delete(webinar)

    db.session.commit()


@job
def follow_up_with_users_who_participated_in_zoom_webinar(since_days=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    For all users who participated in zoom webinars that occur since <since_days> ago
    we will:
     .Update custom attribute 'webinars_attended' on Braze
     .Update custom event 'zoom_webinar_attended' on Braze
     .Change UserWebinarStatus to ATTENDED
    """

    webinars_held_since_date = zoom.get_webinars_since_days_ago(since_days)
    log.info(
        f"Found {len(webinars_held_since_date)} webinars held since {since_days} days ago"
    )
    for webinar in webinars_held_since_date:
        participants = zoom.get_users_who_participated_in_webinar(webinar.id)
        log.info(
            "Found participants for webinar",
            num_of_participants=len(participants),
            webinar_id=webinar.id,
        )
        for participant in participants:
            log.debug(f"Following up with {participant} for webinar ID={webinar.id}")
            braze.track_user_webinars(participant, webinar.topic)
            braze_events.zoom_webinar_followup(
                participant, "zoom_webinar_attended", webinar
            )

            user_webinar = UserWebinar.query.filter_by(
                user_id=participant.id, webinar_id=webinar.id
            ).scalar()
            if user_webinar:
                user_webinar.status = UserWebinarStatus.ATTENDED
                db.session.add(user_webinar)

    db.session.commit()


@job
def follow_up_with_users_who_missed_zoom_webinar(since_days=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    For all users who missed zoom webinars that occur since <since_days> ago
    we will:
     .Update custom attribute 'webinars_attended' on Braze
     .Update custom event 'zoom_webinar_missed' on Braze
     .Change UserWebinarStatus to MISSED
    """

    webinars_held_since_date = zoom.get_webinars_since_days_ago(since_days)
    log.info(
        f"Found {len(webinars_held_since_date)} webinars held since {since_days} days ago"
    )
    for webinar in webinars_held_since_date:
        absentees = zoom.get_users_who_missed_webinar(webinar.id)
        log.info(
            "Found absentees for webinar",
            num_of_participants=len(absentees),
            webinar_id=webinar.id,
        )
        for absentee in absentees:
            log.debug(f"Following up with {absentees} for webinar ID={webinar.id}")
            braze.track_user_webinars(absentee, webinar.topic)
            braze_events.zoom_webinar_followup(absentee, "zoom_webinar_missed", webinar)

            user_webinar = UserWebinar.query.filter_by(
                user_id=absentee.id, webinar_id=webinar.id
            ).scalar()
            if user_webinar:
                user_webinar.status = UserWebinarStatus.MISSED
                db.session.add(user_webinar)

    db.session.commit()
