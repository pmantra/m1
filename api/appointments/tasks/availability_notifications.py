import datetime

from flask import current_app

from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.models.schedule_event import ScheduleEvent
from authz.models.roles import ROLES

# DO NOT REMOVE THE BELOW LINE. SQLALCHEMY NEEDS IT FOR MAPPER INSTANTIATION
from common import stats
from l10n.utils import message_with_enforced_locale
from models.images import Image  # noqa: F401
from models.profiles import Device
from models.referrals import ReferralCodeUse  # noqa: F401
from storage.connection import db
from tasks.queues import job
from utils import braze_events
from utils.apns import apns_send_bulk_message
from utils.constants import (
    MAVEN_SMS_DELIVERY_ERROR,
    SMS_MISSING_PROFILE,
    SMS_MISSING_PROFILE_NUMBER,
    TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
)
from utils.log import logger
from utils.sms import country_accepts_url_in_sms, parse_phone_number, send_sms

log = logger(__name__)


@job
def notify_about_upcoming_availability() -> None:
    """run every 10 mins"""
    now = datetime.datetime.utcnow()
    plus_10 = now + datetime.timedelta(minutes=10)

    avails = (
        db.session.query(ScheduleEvent)
        .filter(ScheduleEvent.starts_at > now, ScheduleEvent.starts_at < plus_10)
        .all()
    )

    log.debug("Got %s avails to notify", len(avails))
    for avail in avails:
        # get the previous event for that schedule if any
        previous = (
            db.session.query(ScheduleEvent)
            .filter(
                ScheduleEvent.starts_at < avail.starts_at,
                ScheduleEvent.schedule_id == avail.schedule_id,
            )
            .order_by(ScheduleEvent.starts_at.desc())
            .first()
        )

        if previous:
            if previous.ends_at == avail.starts_at:
                log.debug(
                    "This avail (%s) is contiguous with previous (%s)", avail, previous
                )
            else:
                log.debug("This is the start of a new availability: %s", avail)

                user = avail.schedule.user

                avail_starts_in = (
                    int(((avail.starts_at - now).total_seconds()) / 60) + 1
                )
                push_message = f"You have upcoming availability on Maven in {avail_starts_in} minutes"
                devices = Device.for_user(user, ROLES.practitioner)
                device_ids = [d.device_id for d in devices]

                log.debug(
                    "Sending user [%s] a push notification: %s",
                    user.id,
                    push_message,
                )
                apns_send_bulk_message(
                    device_ids, alert=push_message, application_name=ROLES.practitioner
                )
                braze_events.notify_upcoming_availability(
                    avail.schedule.user, avail_starts_in
                )


@job("priority", traced_parameters=("practitioner_id",))
def notify_about_availability(practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    pending_requests = (
        db.session.query(AvailabilityNotificationRequest)
        .filter(
            AvailabilityNotificationRequest.practitioner_id == practitioner_id,
            AvailabilityNotificationRequest.notified_at.is_(None),
            AvailabilityNotificationRequest.cancelled_at.is_(None),
        )
        .all()
    )

    log.debug(
        "Got %s availability notifications to send for prac <%s>",
        len(pending_requests),
        practitioner_id,
    )
    for request in pending_requests:
        log.debug("Notifying for %s", request)

        user = request.member
        mp = user.member_profile

        if not mp:
            log.warning(
                "Unable to send SMS for new practitioner availability - profile unavailable",
                user_id=user.id,
                user_role=ROLES.member,
            )
            stats.increment(
                metric_name=SMS_MISSING_PROFILE,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.member}",
                    "source:notify_about_availability",
                ],
            )
            continue
        elif not mp.phone_number:
            log.warning(
                "Unable to send SMS for new practitioner availability - profile number unavailable",
                user_id=user.id,
                user_role=ROLES.member,
            )

            stats.increment(
                metric_name=SMS_MISSING_PROFILE_NUMBER,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.member}",
                    "source:notify_about_availability",
                ],
            )
            continue
        else:
            practitioner_name = request.practitioner.full_name
            message = message_with_enforced_locale(
                user=user,
                text_key="notify_member_about_new_prac_availability_url_disabled",
            ).format(practitioner_name=practitioner_name)

            parsed_phone_number = parse_phone_number(mp.phone_number)
            if not parsed_phone_number or country_accepts_url_in_sms(
                parsed_phone_number
            ):
                message = message_with_enforced_locale(
                    user=user,
                    text_key="notify_member_about_new_prac_availability_url_enabled",
                ).format(
                    practitioner_name=practitioner_name,
                    url=current_app.config["BASE_URL"],
                    practitioner_id=practitioner_id,
                )
            try:
                result = send_sms(
                    message=message,
                    to_phone_number=mp.phone_number,
                    user_id=mp.user_id,
                    notification_type="appointments",
                )
            except Exception as e:
                log.exception(
                    "Exception found when attempting to send SMS notification to member about new practitioner availability",
                    user_id=mp.id,
                    exception=e,
                )

                stats.increment(
                    metric_name=MAVEN_SMS_DELIVERY_ERROR,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=[
                        "result:failure",
                        "notification_type:appointments",
                        "reason:maven_server_exception",
                        "source:notify_about_availability",
                    ],
                )
                continue
            if result.is_ok:
                log.info(
                    "Sent SMS notification to member about new practitioner availability",
                    user_id=mp.user_id,
                )
                request.notified_at = datetime.datetime.utcnow()
                db.session.add(request)
                stats.increment(
                    metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=["result:success", "notification_type:appointments"],
                )
            else:
                if result.is_blocked:
                    log.warning(
                        "Could not notify via SMS. SMS is blocked for the user",
                        user_id=mp.user_id,
                    )
                    db.session.add(mp)
                    mp.mark_as_sms_blocked(result.error_code)
            db.session.commit()

        braze_events.practitioner_set_availability(request.member, request.practitioner)

        log.debug("All set notifying member for %s", request)

    log.info("Notified about all pending notifications for prac <%s>", practitioner_id)
