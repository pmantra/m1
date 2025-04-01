from models.zoom import UserWebinar, UserWebinarStatus, Webinar
from storage.connection import db
from utils import braze, braze_events, zoom
from utils.log import logger

log = logger(__name__)


def follow_up_with_users_who_participated_in_zoom_webinar():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    For all users who have ever participated in zoom webinars
    we will:
     .Update custom attribute 'webinars_attended' on Braze
     .Update custom event 'zoom_webinar_attended' on Braze
     .Change UserWebinarStatus to ATTENDED
    """

    all_webinars = Webinar.query.all()
    log.debug(f"Found {len(all_webinars)} webinars")

    for webinar in all_webinars:
        participants = zoom.get_users_who_participated_in_webinar(webinar.id)
        log.debug(f"Found {len(participants)} participants for webinar ID={webinar.id}")
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


def follow_up_with_users_who_missed_zoom_webinar():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    For all users who have ever missed a zoom webinars
    we will:
     .Update custom attribute 'webinars_attended' on Braze
     .Update custom event 'zoom_webinar_missed' on Braze
     .Change UserWebinarStatus to MISSED
    """

    all_webinars = Webinar.query.all()
    log.debug(f"Found {len(all_webinars)} webinars")

    for webinar in all_webinars:
        absentees = zoom.get_users_who_missed_webinar(webinar.id)
        log.debug(f"Found {len(absentees)} absentees for webinar ID={webinar.id}")
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


if __name__ == "__main__":
    follow_up_with_users_who_participated_in_zoom_webinar()
    follow_up_with_users_who_missed_zoom_webinar()
