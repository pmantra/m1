from __future__ import annotations

from traceback import format_exc

from direct_payment.notification.models import NotificationPayload
from direct_payment.notification.notification_service import NotificationService
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job(service_ns="direct_payment", team_ns="benefits_experience")
def send_notification_event(
    user_id: str,
    user_id_type: str,
    user_type: str | None,
    event_source_system: str,
    event_name: str,
    event_properties: dict,
) -> None:
    """
    :param user_id: The user id as known by the calling system - used for lookup .
    :param user_id_type: The type of the user id - used for lookup
    :param user_type: The type of the user - added for future support of employers/clinics
    :param event_source_system: The system calling the service - used for logging.
    :param event_name: The event name registered in Braze.
    :param event_properties: The properties for this event
    """
    try:
        res = NotificationService().send_notification_event(
            user_id=user_id,
            user_id_type=user_id_type,
            user_type=user_type,
            event_source_system=event_source_system,
            event_name=event_name,
            event_properties=event_properties,
        )
        log.info(
            "Sent notification event to braze",
            user_id=str(user_id),
            user_id_type=user_id_type,
            event_source_system=event_source_system,
            event_name=event_name,
            event_properties=event_properties,
            res=res,
        )
    except Exception:
        log.error(
            "Unable to send MMB notification",
            reason=format_exc(),
            user_id=str(user_id),
            user_id_type=user_id_type,
            event_source_system=event_source_system,
            event_name=event_name,
            event_properties=event_properties,
        )


@job(service_ns="direct_payment", team_ns="benefits_experience")
def send_notification_event_from_payload(payload: NotificationPayload) -> None:
    """
    :param payload: The notification payload.
    """
    try:
        res = NotificationService().send_notification_event_from_payload(payload)
        log.info(f"Sent notification event. Result: {res}")
    except Exception:
        # TODO slack notification over here.
        log.error(
            "Unable to send MMB notification", reason=format_exc(), payload=payload
        )
