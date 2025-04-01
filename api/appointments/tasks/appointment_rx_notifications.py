import datetime

from appointments.models.appointment import Appointment

# DO NOT REMOVE THE BELOW LINE. SQLALCHEMY NEEDS IT FOR MAPPER INSTANTIATION
from authz.models.roles import ROLES
from common import stats
from l10n.utils import message_with_enforced_locale
from models.images import Image  # noqa: F401
from models.profiles import Device
from models.referrals import ReferralCodeUse  # noqa: F401
from storage.connection import db
from tasks.helpers import get_appointment
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
from utils.sms import send_sms

log = logger(__name__)


@job
def notify_about_recently_written_rx() -> None:
    now = datetime.datetime.utcnow()
    m_hours = now - datetime.timedelta(hours=2)

    to_notify = (
        db.session.query(Appointment)
        .filter(Appointment.rx_written_at.between(m_hours, now))
        .all()
    )
    log.debug("Got %d appts with rx written in last 2 hours.", len(to_notify))

    for appointment in to_notify:
        notify_about_rx_complete.delay(appointment.id, team_ns="virtual_care")


@job(traced_parameters=("appointment_id",))
def notify_about_rx_complete(appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    noti_key = "notified:rx_written"
    call_notify_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=30)

    appointment = get_appointment(appointment_id)
    if appointment:
        if appointment.json.get(noti_key):
            log.debug(
                "Already notified rx written for Appointment: (%s)", appointment.id
            )
            return

        ready_to_notify = False
        rx_written_via = appointment.rx_written_via
        rx_written_at = appointment.rx_written_at

        if (rx_written_via == "call") and rx_written_at < call_notify_time:
            ready_to_notify = True
        elif rx_written_via == "dosespot":
            ready_to_notify = appointment.is_rx_ready

        if not ready_to_notify:
            log.debug(
                "Not ready to notify yet for rx written for Appointment: (%s)",
                appointment.id,
            )
            return

        log.info(
            "Going to notify about RX written for Appointment: (%s)", appointment.id
        )
        user = appointment.member
        mp = user.member_profile
        if not mp:
            log.warning(
                "Unable to send SMS for RX written for appointment - profile unavailable",
                appointment_id=appointment.id,
                user_id=appointment.member.id,
                user_role=ROLES.member,
            )
            stats.increment(
                metric_name=SMS_MISSING_PROFILE,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.member}",
                    "source:notify_about_rx_complete",
                ],
            )
        elif not mp.phone_number:
            log.warning(
                "Unable to send SMS for RX written for appointment - profile number unavailable",
                appointment_id=appointment.id,
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
                    "source:notify_about_rx_complete",
                ],
            )
        else:
            pharmacy_info = mp.get_prescription_info().get("pharmacy_info", {})
            if not pharmacy_info:
                log.info(
                    (
                        "No pharmacy_info for Appointment: (%s) in rx complete noti - not "
                        "sending."
                    ),
                    appointment.id,
                )
                return

            pharmacy_name = pharmacy_info.get("StoreName", "").title()
            pharmacy_phone = pharmacy_info.get("PrimaryPhone")
            message = message_with_enforced_locale(
                user=user, text_key="notify_member_about_written_rx"
            ).format(pharmacy_name=pharmacy_name, pharmacy_phone=pharmacy_phone)
            try:
                result = send_sms(
                    message=message,
                    to_phone_number=mp.phone_number,
                    user_id=mp.user_id,
                    notification_type="appointments",
                )
            except Exception as e:
                log.exception(
                    "Exception found when attempting to send SMS notification for appointment",
                    appointment_id=appointment.id,
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
                        "source:notify_about_rx_complete",
                    ],
                )
                return None
            if result.is_ok:
                log.info(
                    "Sent SMS Notification to Member about RX info written for appointment",
                    user_id=mp.user_id,
                )
                stats.increment(
                    metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=["result:success", "notification_type:appointments"],
                )
            if result.is_blocked:
                log.debug(
                    "Member Profile: (%s) has phone number that is sms blocked: %s",
                    mp.id,
                    result.error_message,
                )
                db.session.add(mp)
                mp.mark_as_sms_blocked(result.error_code)

            practitioner_devices = Device.for_user(
                appointment.practitioner, "practitioner"
            )
            device_ids = [d.device_id for d in practitioner_devices]

            if device_ids:
                apns_send_bulk_message(
                    device_ids,
                    (
                        f"We've let {appointment.member_name} know that you have submitted their prescription. "
                        "Thanks!"
                    ),
                    application_name="practitioner",
                    extra={"link": f"maven://appointment/{appointment.api_id}"},
                )
                braze_events.prescription_sent(
                    appointment, pharmacy_name, pharmacy_phone, rx_written_at
                )

            appointment.json[noti_key] = str(datetime.datetime.utcnow())
            db.session.add(appointment)
            db.session.commit()
