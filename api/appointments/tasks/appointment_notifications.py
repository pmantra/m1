from __future__ import annotations

import datetime

import ddtrace
from flask import current_app
from maven import feature_flags

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES, AppointmentTypes
from appointments.models.member_appointment import MemberAppointmentAck
from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.utils.appointment_utils import convert_time_to_message_str
from authz.models.roles import ROLES
from common import stats
from common.stats import PodNames
from l10n.utils import message_with_enforced_locale
from models.profiles import Device, MemberProfile, PractitionerProfile
from storage.connection import db
from tasks.helpers import get_appointment
from tasks.queues import job, retryable_job
from tracks import service as tracks_svc
from utils import braze_events
from utils.apns import apns_send_bulk_message
from utils.constants import (
    MAVEN_SMS_DELIVERY_ERROR,
    SMS_MISSING_PROFILE,
    SMS_MISSING_PROFILE_NUMBER,
    TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
)
from utils.flag_groups import APPOINTMENT_NOTIFICATIONS
from utils.launchdarkly import user_context
from utils.log import logger
from utils.slack import notify_bookings_channel, notify_enterprise_bookings_channel
from utils.slack_v2 import notify_vip_bookings_channel
from utils.sms import (
    cancel_sms,
    country_accepts_url_in_sms,
    parse_phone_number,
    send_sms,
)

BOOKINGS_ENTERPRISE_VIP_ORGANIZATION = "VIP_Test_Accounts_Primary"
BRAZE_UPCOMING_APPT_REMINDER_24H = "appointment_reminder_member"
BRAZE_UPCOMING_APPT_REMINDER_1H = "appointment_reminder_member_1h"

# default search window for upcoming appointment reminder
APPOINTMENT_NOTIFICATION_REMINDER_TIME_DEFAULT = 60

# buffer for cron job timing
APPOINTMENT_NOTIFICATION_REMINDER_BUFFER = 10  # in minutes

log = logger(__name__)

TWILIO_MINIMUM_SEND_AT_DELAY = 900


@job("priority", traced_parameters=("appointment_id",))
@ddtrace.tracer.wrap()
def notify_about_new_appointment(appointment_id: int) -> None:
    """
    We're scheduling jobs to send 4 notification types here:
        - push
        - email
        - SMS (if they have a valid phone #)
        - slack (for internal use by the Maven team in #bookings)
    """
    correlation_context = ddtrace.tracer.get_log_correlation_context()
    trace_context = dict(
        appointment_id=appointment_id,
        task="notify_about_new_appointment",
    )
    ddtrace.tracer.set_tags(trace_context)
    log_context = {**correlation_context, **trace_context}
    metric_tags = {f"{k}:{v}" for k, v in log_context.items()}
    log.info("Trying to notify for new appointment.", **log_context)
    appointment = get_appointment(appointment_id)
    if not appointment:
        log.warning("No appointment to notify for new.", **log_context)
        stats.increment(
            "notifications.appointment_not_found",
            pod_name=stats.PodNames.MPRACTICE_CORE,
            tags=[*metric_tags],
        )
        return

    appointment_state = appointment.state
    appointment_api_id = appointment.api_id
    new_context = dict(
        practitioner_id=appointment.practitioner and appointment.practitioner.id,
        user_id=appointment.member and appointment.member.id,
        appointment_state=appointment_state,
        appointment_api_id=appointment_api_id,
    )
    ddtrace.tracer.set_tags(new_context)
    log_context.update(new_context)
    metric_tags.update(f"{k}:{v}" for k, v in new_context.items())
    if appointment_state != APPOINTMENT_STATES.scheduled:
        log.warning("Not going to notify (not scheduled state).", **log_context)
        stats.increment(
            "notifications.appointment_wrong_state",
            pod_name=stats.PodNames.MPRACTICE_CORE,
            tags=[*metric_tags],
        )
        return

    # sms notify member about new appointment booking
    if feature_flags.bool_variation(
        APPOINTMENT_NOTIFICATIONS.SMS_NOTIFY_MEMBER_ABOUT_NEW_APPOINTMENT,
        user_context(appointment.member),
        default=False,
    ):
        sms_notify_member_about_new_appointment(appointment=appointment)

    # slack
    notify_bookings_about_new_appointment.delay(appointment_id)

    # practitioner email
    confirm_booking_email_to_practitioner.delay(appointment_id, log_context)

    profile = appointment.practitioner.practitioner_profile
    if not profile:
        log.warning(
            "Unable to send SMS for upcoming appointment - profile unavailable",
            appointment_id=appointment.id,
            user_id=appointment.member.id,
            user_role=ROLES.practitioner,
        )
        stats.increment(
            metric_name=SMS_MISSING_PROFILE,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                f"user_role:{ROLES.practitioner}",
                "source:notify_about_new_appointment",
            ],
        )
        return

    # DO NOT send SMS or Push notifications to CAs
    if not profile.is_cx:
        # practitioner push notifications
        confirm_booking_push_notifications_to_practitioner.delay(
            appointment_id, appointment_api_id, correlation_context
        )
        # text
        confirm_booking_sms_notifications_to_practitioner.delay(
            appointment_id, appointment_api_id, log_context, team_ns="virtual_care"
        )


@retryable_job("priority", retry_limit=3, team_ns="virtual_care")
def notify_bookings_about_new_appointment(appointment_id: int) -> None:
    appointment = get_appointment(appointment_id)
    try:
        _notify_bookings_channel(appointment)
    except ValueError as e:
        log.warning("Error in notify_bookings_about_new_appointment", exception=str(e))


def sms_notify_member_about_new_appointment(appointment: Appointment) -> None:

    member = appointment.member
    user_id = member.id
    profile = member.profile

    if not profile:
        log.warning(
            "Unable to send SMS for newly booked appointment - profile unavailable",
            appointment_id=appointment.id,
            user_id=user_id,
            user_role=ROLES.member,
        )
        stats.increment(
            metric_name=SMS_MISSING_PROFILE,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                f"user_role:{ROLES.member}",
                "source:sms_notify_member_about_new_appointment",
            ],
        )

        return None

    phone_number = profile.phone_number
    if not phone_number:
        log.warning(
            "Unable to send SMS for newly booked appointment - profile number unavailable",
            appointment_id=appointment.id,
            user_id=user_id,
            user_role=ROLES.member,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE_NUMBER,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                f"user_role:{ROLES.member}",
                "source:sms_notify_member_about_new_appointment",
            ],
        )
        return None

    # sms message
    message = message_with_enforced_locale(
        user=member, text_key="sms_notify_member_about_new_appointment"
    )

    parsed_phone_number = parse_phone_number(phone_number)

    # if we were unable to parse the phone number we adhere to the default condition of including the url
    if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
        cta = message_with_enforced_locale(
            user=member, text_key="cta_sms_notify_member_about_new_appointment_link_url"
        ).format(url=f"{current_app.config['BASE_URL']}/my-appointments")
        message = f"{message} {cta}"
    else:
        cta = message_with_enforced_locale(
            user=member, text_key="cta_sms_notify_member_about_new_appointment_no_url"
        )
        message = f"{message} {cta}"

    try:
        result = send_sms(
            message=message,
            to_phone_number=profile.phone_number,
            user_id=profile.user_id,
            notification_type="appointments",
            appointment_id=appointment.id,
        )
    except Exception as e:
        log.exception(
            "Exception found when attempting to send SMS notification for appointment",
            appointment_id=appointment.id,
            user_id=profile.user_id,
            exception=e,
        )
        stats.increment(
            metric_name=MAVEN_SMS_DELIVERY_ERROR,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                "reason:maven_server_exception",
                "source:sms_notify_member_about_new_appointment",
            ],
        )
        return None
    if result.is_ok:
        log.info(
            "Successfully sent appointment confirmation SMS to Member",
            user_id=profile.user_id,
            appointment_id=appointment.id,
        )
        stats.increment(
            metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["result:success", "notification_type:appointments"],
        )
    else:
        log.warning(
            "Couldn't send appointment confirmation SMS to Member", user_id=user_id
        )
        if result.is_blocked:
            log.warning(
                "Member Profile has a phone number that is sms blocked",
                user_id=profile.user_id,
                error_message=result.error_message,
            )
            db.session.add(profile)
            profile.mark_as_sms_blocked(result.error_code)
            db.session.commit()
        return


def _notify_bookings_channel(appointment: Appointment) -> None:
    if not appointment or not appointment.practitioner:
        raise ValueError("Appointment or practitioner is missing")

    profile = appointment.practitioner.practitioner_profile
    phone_no = profile.phone_number

    practitioner_info = f"{appointment.practitioner.full_name} [{appointment.practitioner.email}]{phone_no if phone_no else ''}"
    internal_string = (
        "Internal"
        if appointment.member.email.endswith("mavenclinic.com")
        else "External"
    )

    track_svc = tracks_svc.TrackSelectionService()
    organization = track_svc.get_organization_for_user(user_id=appointment.member.id)

    if organization and organization.name.lower() != "maven_clinic":
        internal_string = f"{internal_string} ({organization.name})"

    admin_link = f"https://admin.production.mvnctl.net:444/admin/appointment/edit/?id={appointment.id}"

    template = (
        "ID: <{admin_link}|{appointment_id}> ({code}). Starts in {starts_in} "
        "w/ {practitioner_info} - Booking is {internal_string}"
    )

    _code = appointment.user_recent_code
    if _code:
        _clean = _code.lower()
        if _clean.startswith("teammaven") or _clean.startswith("summerofmaven"):
            cleaned_code = None
        else:
            cleaned_code = _code
    else:
        cleaned_code = None

    message = template.format(
        admin_link=admin_link,
        appointment_id=appointment.id,
        starts_in=appointment.starts_in(),
        practitioner_info=practitioner_info,
        internal_string=internal_string,
        code=cleaned_code,
    )

    notify_bookings_channel(message)
    if track_svc.is_enterprise(user_id=appointment.member.id):
        notify_enterprise_bookings_channel(message)
        vip_title = "VIP Appointment Notification"
        notify_vip_bookings(appointment.member, vip_title, message)


@retryable_job("priority", retry_limit=3, team_ns="virtual_care")
@ddtrace.tracer.wrap()
def confirm_booking_push_notifications_to_practitioner(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    appointment_id: int,
    appointment_api_id: int,
    correlation_context: dict[str, str],
):
    appointment = get_appointment(appointment_id)
    practitioner_id = appointment.practitioner_id
    ddtrace.tracer.set_tags(correlation_context)
    device_ids = []
    for device in Device.for_user(appointment.practitioner, "practitioner"):
        device_ids.append(device.device_id)

    if not device_ids:
        log.info(
            "No device IDs to notify practitioner for new appointment.",
            appointment_id=appointment_id,
            practitioner_id=practitioner_id,
            **correlation_context,
        )
        return
    try:
        with ddtrace.tracer.trace("notifications.send_via_apns") as span:
            for device_id in device_ids:
                span.set_tag(f"maven.device_id:{device_id}")
            apns_send_bulk_message(
                device_ids,
                f"{appointment.member_name} booked an appointment!".capitalize(),
                application_name="practitioner",
                extra={"link": f"maven://appointment/{appointment_api_id}"},
            )
    except Exception as e:
        log.error(
            "Problem sending practitioner notification via APNS.",
            error_message=str(e),
            error_type=e.__class__.__name__,
            device_ids=device_ids,
            appointment_id=appointment_id,
            practitioner_id=practitioner_id,
            **correlation_context,
        )


@retryable_job(
    "priority",
    retry_limit=3,
)
@ddtrace.tracer.wrap()
def confirm_booking_sms_notifications_to_practitioner(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    appointment_id: int,
    appointment_api_id: int,
    log_context: dict[str, str],
):
    ddtrace.tracer.set_tags(log_context)
    appointment = get_appointment(appointment_id)
    user = appointment.practitioner
    user_id = user.id
    profile = user.practitioner_profile

    if not profile.phone_number:
        log.warning(
            "Unable to send SMS for upcoming appointment - profile number unavailable",
            appointment_id=appointment.id,
            user_id=user.id,
            user_role=ROLES.practitioner,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE_NUMBER,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                f"user_role:{ROLES.practitioner}",
                "source:confirm_booking_sms_notifications_to_practitioner",
            ],
        )
        return None
    message = (
        f"You have a new appointment on Maven (starting in {appointment.starts_in()})! "
        "If you cannot make it, please cancel in the MPractice iOS app."
    )

    phone_number = profile.phone_number
    parsed_phone_number = parse_phone_number(phone_number)

    # if we were unable to parse the phone number we adhere to the default condition of including the url
    if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
        deeplink = (
            f"{current_app.config['BASE_URL']}/mp_/my-appointments/{appointment_api_id}"
        )
        message = message + f" Appt details here: {deeplink}"

    with ddtrace.tracer.trace("notifications.send_appointment_reminder"):
        try:
            result = send_sms(
                message=message,
                to_phone_number=phone_number,
                user_id=user_id,
                send_at=None,
                # type: ignore[arg-type] # Argument "send_at" to "send_sms" has incompatible type "None"; expected "datetime"
                pod=PodNames.VIRTUAL_CARE,
                notification_type="appointments",
                appointment_id=appointment_id,
            )
        except Exception as e:
            log.exception(
                "Exception found when attempting to send SMS notification for appointment",
                appointment_id=appointment_id,
                user_id=user_id,
                exception=e,
            )

            stats.increment(
                metric_name=MAVEN_SMS_DELIVERY_ERROR,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    "reason:maven_server_exception",
                    "source:confirm_booking_sms_notifications_to_practitioner",
                ],
            )

            return None

    sms_context = {
        "sms.is_ok": result.is_ok,
        "sms.is_blocked": result.is_blocked,
        "sms.error_code": result.error_code,
        "sms.error_message": result.error_message,
    }
    ddtrace.tracer.set_tags(sms_context)

    if result.is_ok:
        log.info("Sent SMS to practitioner for new appointment", **log_context)
        stats.increment(
            metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["result:success", "notification_type:appointments"],
        )
        return
    log.info(
        "Couldn't notify practitioner via SMS for new appointment",
        error_code=result.error_code or None,
        error_message=result.error_message or None,
        **log_context,
    )
    if result.is_blocked:
        log.info(
            "Phone number is sms blocked.",
            error_message=result.error_message,
            **log_context,
        )
        db.session.add(profile)
        profile.mark_as_sms_blocked(result.error_code)
        db.session.commit()
        return
    if result.error_code:
        log.info(
            f"Error sending SMS to practitioner for new appointment {appointment.id}",
            error_code=result.error_code,
            error_message=result.error_message or None,
            **log_context,
        )


@retryable_job(
    "priority",
    retry_limit=3,
    traced_parameters=("appointment_id",),
    team_ns="virtual_care",
)
def confirm_booking_email_to_member(appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    appointment: Appointment = get_appointment(appointment_id)

    if not appointment:
        log.warning("No appointment to notify for confirm: %s", appointment_id)
        return

    braze_events.appointment_booked_member(appointment)


@retryable_job(
    "priority",
    retry_limit=3,
    traced_parameters=("appointment_id",),
    team_ns="virtual_care",
)
@ddtrace.tracer.wrap()
def confirm_booking_email_to_practitioner(appointment_id, log_context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    ddtrace.tracer.set_tags(log_context)
    appointment: Appointment = get_appointment(appointment_id)

    if not appointment:
        log.warning(
            "No appointment to notify for confirm: %s", appointment_id, **log_context
        )
        return

    braze_events.appointment_booked_practitioner(appointment)


@retryable_job("priority", retry_limit=3, team_ns="virtual_care")
def remind_members_about_advance_bookings() -> None:
    now = datetime.datetime.utcnow()

    # appointments created more than 12 hours ago,
    # which start in less than 24 hours but more than 23 hours
    # which are not cancelled and haven't been notified about yet
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start > now + datetime.timedelta(hours=23),
            Appointment.scheduled_start < now + datetime.timedelta(hours=24),
            Appointment.created_at < now - datetime.timedelta(hours=12),
            Appointment.cancelled_at.is_(None),
            Appointment.reminder_sent_at.is_(None),
        )
        .all()
    )

    log.info("Got %s appointments to notify about advance booking", len(appointments))
    for appointment in appointments:
        log.debug(
            (
                f"Current time: {now}. Appointment time: {appointment.scheduled_start} "
                f"Appointment created time: {appointment.created_at}"
            )
        )
        braze_events.appointment_reminder_member(
            appointment=appointment, event_name=BRAZE_UPCOMING_APPT_REMINDER_24H
        )
        appointment.reminder_sent_at = now
        db.session.commit()


@job("priority")
def notify_about_upcoming_noshows() -> None:
    now = datetime.datetime.utcnow()

    upcoming = (
        db.session.query(PractitionerAppointmentAck)
        .filter(
            PractitionerAppointmentAck.ack_by <= now,
            PractitionerAppointmentAck.is_acked == False,
            PractitionerAppointmentAck.is_alerted == False,
        )
        .all()
    )

    track_svc = tracks_svc.TrackSelectionService()

    log.debug("Got upcoming noshows: %s", upcoming)
    for ack in upcoming:
        if ack.appointment.cancelled_at:
            log.debug("Appointment is cancelled, not a no-show...")

            # mark alerted since we don't want to alert here
            ack.is_alerted = True
            db.session.add(ack)
            db.session.commit()
            continue

        log.debug("Alerting for upcoming noshow for %s", ack.appointment)

        tmpl = (
            "<!channel> Appointment {id} upcoming practitioner no-show "
            "for {practitioner_name} - ({phone_number})"
        )

        practitioner = ack.appointment.practitioner
        message = tmpl.format(
            id=ack.appointment.id,
            practitioner_name=practitioner.full_name,
            phone_number=ack.phone_number,
        )
        notify_bookings_channel(message)

        if track_svc.is_enterprise(user_id=ack.appointment.member.id):
            notify_enterprise_bookings_channel(message)
            vip_title = "VIP Appointment No-show"
            notify_vip_bookings(ack.appointment.member, vip_title, message)

        ack.is_alerted = True
        db.session.add(ack)
        db.session.commit()

        log.debug("Alerted channel about upcoming noshow for %s", ack.appointment)


@retryable_job("priority", retry_limit=3, team_ns="virtual_care")
def sms_notify_upcoming_appointments_member() -> None:
    """
    Job that notifies members about upcoming appointments using SMS.
    """
    application_name = ROLES.member

    # get upcoming appointments
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start > datetime.datetime.utcnow(),
            Appointment.scheduled_start
            <= datetime.datetime.utcnow() + datetime.timedelta(minutes=2),
            Appointment.cancelled_at == None,
        )
        .all()
    )

    if not appointments:
        log.info(
            f"No upcoming appointments that require notify action for {application_name}"
        )

    for appointment in appointments:
        if not appointment.state == APPOINTMENT_STATES.scheduled:
            log.info(
                f"Appointment {appointment.id} not scheduled - unable to notify for upcoming appointment"
            )
            continue

        # determine if the user was already notified
        notified = False
        push_key = _get_push_key(application_name)
        sms_key = _get_sms_key(application_name)
        keys = [push_key, sms_key]
        for notification_key in keys:
            if appointment.json.get(notification_key):
                log.info(
                    f"Already notified {application_name} for appointment {appointment.id}",
                    notification_key=notification_key,
                )
                notified = True
                break

        if notified:
            continue

        log.info(
            "Attempting to send SMS to member for upcoming appointment",
            appointment_id=appointment.id,
        )

        # get profile
        profile: MemberProfile | PractitionerProfile
        user = appointment.member
        profile = user.member_profile
        if not profile:
            log.warning(
                "Unable to send SMS for upcoming appointment - profile unavailable",
                application_name=application_name,
                appointment_id=appointment.id,
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
                    "source:sms_notify_upcoming_appointments_member",
                ],
            )
            continue

        elif not profile.phone_number:
            log.warning(
                "Unable to send SMS for upcoming appointment - profile number unavailable",
                application_name=application_name,
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
                    "source:sms_notify_upcoming_appointments_member",
                ],
            )
            continue

        # sms message
        message = message_with_enforced_locale(
            user=user, text_key="notify_member_upcoming_appointment"
        ).format(appointment_start_time_remaining=appointment._starts_in_minutes())

        phone_number = profile.phone_number
        parsed_phone_number = parse_phone_number(phone_number)
        # if we were unable to parse the phone number we adhere to the default condition of including the url
        if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
            cta_link = message_with_enforced_locale(
                user=user, text_key="cta_notify_member_upcoming_appointment_link"
            ).format(url=f"{current_app.config['BASE_URL']}/my-appointments")
            message = f"{message} {cta_link}"

        _send_sms_upcoming_appointment(
            appointment, profile, sms_key, application_name, message
        )


@ddtrace.tracer.wrap()
@retryable_job("priority", retry_limit=3, team_ns="virtual_care")
def schedule_member_appointment_confirmation(
    appointment_id: int,
) -> MemberAppointmentAck | None:
    """
    Schedules a confirmation SMS message to be sent to the appointment member 24 hours before the scheduled start of the appointment.
    Only sends for appointments that were scheduled 24 hours or more in advance.
    """
    appointment: Appointment = get_appointment(appointment_id)
    if not appointment:
        log.warning(
            "Unable to schedule member appointment confirmation, provided appointment id not found",
            appointment_id=appointment_id,
        )
        return None

    app_confirmation_enabled_all_verticals = feature_flags.bool_variation(
        APPOINTMENT_NOTIFICATIONS.CONFIRM_APPOINTMENT_SMS,
        user_context(appointment.member),
        default=False,
    )
    app_confirmation_enabled_ca = feature_flags.bool_variation(
        APPOINTMENT_NOTIFICATIONS.CONFIRM_APPOINTMENT_SMS_CA,
        user_context(appointment.member),
        default=False,
    )
    meets_pilot_criteria = appointment_meets_pilot_criteria(appointment)

    # 2 pilots - one FFlag for pilot verticals, one fflag for CA vertical
    if not (app_confirmation_enabled_all_verticals and meets_pilot_criteria) and not (
        app_confirmation_enabled_ca
        and appointment.product.vertical.name == "Care Advocate"
    ):
        return None

    existing_ack = MemberAppointmentAck.query.filter(
        MemberAppointmentAck.appointment_id == appointment_id
    ).all()

    # Only create an ack for an appointment if one has not been created
    if existing_ack:
        return None

    # dont send confirmations to users when the appt is scheduled within 24hours
    # of its scheduled start time
    if appointment.scheduled_start < appointment.created_at + datetime.timedelta(
        hours=24
    ):
        return None

    member = appointment.member
    member_user_id = member.id
    member_profile = member.member_profile
    if not member_profile:
        log.warning(
            "Unable to send SMS for upcoming appointment - profile unavailable",
            appointment_id=appointment.id,
            user_id=member_user_id,
            user_role=ROLES.member,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                f"user_role:{ROLES.member}",
                "source:schedule_member_appointment_confirmation",
            ],
        )
        return None
    elif not member_profile.phone_number:
        log.warning(
            "Unable to send SMS for upcoming appointment - profile number unavailable",
            appointment_id=appointment.id,
            user_id=member_user_id,
            user_role=ROLES.member,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE_NUMBER,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                f"user_role:{ROLES.member}",
                "source:schedule_member_appointment_confirmation",
            ],
        )
        return None

    phone_number = member_profile.phone_number
    send_at = appointment.scheduled_start - datetime.timedelta(hours=24)
    member_ack = MemberAppointmentAck(
        appointment=appointment,
        phone_number=phone_number,
        user=member,
        is_acked=False,
    )
    now = datetime.datetime.utcnow()
    # Only send message if the send_at time is between 15 mins and 7 days from now
    if send_at < now + datetime.timedelta(
        days=7
    ) and send_at > now + datetime.timedelta(minutes=15):
        res = schedule_member_appointment_confirmation_sms(
            phone_number, appointment, member_user_id=member_user_id
        )

        if bool(res):
            member_ack.confirm_message_sid = res._result.sid

    db.session.add(member_ack)
    db.session.commit()
    return member_ack


# Verticals that are included in the comfirmation sms pilot
CONFIRM_APPOINTMENT_SMS_VERTICALS = ["OB-GYN", "Pediatrician", "Mental Health Provider"]


def appointment_meets_pilot_criteria(appointment: Appointment) -> bool:
    """
    Check the appointment to ensure that it qualifies for the confirmation sms pilot.

    This function should be removed when the pilot is over
    """
    vertical = appointment.product.vertical
    return (
        appointment.appointment_type == AppointmentTypes.STANDARD
        and vertical.name in CONFIRM_APPOINTMENT_SMS_VERTICALS
    )


def schedule_member_appointment_confirmation_sms(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    phone_number: str,
    appointment: Appointment,
    member_user_id: int,
):
    message = message_with_enforced_locale(
        appointment.member, "member_24_hour_reminder_sms"
    )

    parsed_phone_number = parse_phone_number(phone_number)
    # if we were unable to parse the phone number we adhere to the default condition of including the url
    if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
        cta_link = message_with_enforced_locale(
            user=appointment.member,
            text_key="cta_sms_notify_member_about_new_appointment_link_url",
        ).format(url=f"{current_app.config['BASE_URL']}/my-appointments")
        message = f"{message} {cta_link}"
    else:
        cta = message_with_enforced_locale(
            user=appointment.member,
            text_key="cta_sms_notify_member_about_new_appointment_no_url",
        )
        message = f"{message} {cta}"

    appointment_scheduled_start = appointment.scheduled_start
    current_time = datetime.datetime.utcnow()

    if appointment_scheduled_start < current_time:
        log.info(
            "Appointment scheduled_at time is past the current time. Not sending overdue notification to member.",
            appointment_id=appointment.id,
            member_id=member_user_id,
        )
        return None

    send_at = appointment_scheduled_start - datetime.timedelta(hours=24)

    # Twilio requires `SendAt` time to be between 900 seconds and 35 days (3024000 seconds) in the future (inclusive)
    # relative to the time of the API request (https://www.twilio.com/docs/api/errors/35114)
    if send_at < current_time + datetime.timedelta(
        seconds=TWILIO_MINIMUM_SEND_AT_DELAY
    ):
        # If `send_at` is too soon or in the past, adjust it to 15 minutes in the future
        log.info(
            "Member appointment confirmation send_at time is too soon or in the past - adjusting..."
        )
        send_at = current_time + datetime.timedelta(
            seconds=TWILIO_MINIMUM_SEND_AT_DELAY
        )

    try:
        res = send_sms(
            message=message,
            to_phone_number=phone_number,
            user_id=member_user_id,
            send_at=send_at,
            notification_type="appointments",
            appointment_id=appointment.id,
        )
    except Exception as e:
        log.exception(
            "Exception found when attempting to send SMS notification for appointment",
            appointment_id=appointment.id,
            user_id=member_user_id,
            exception=e,
        )

        stats.increment(
            metric_name=MAVEN_SMS_DELIVERY_ERROR,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                "reason:maven_server_exception",
                "source:schedule_member_appointment_confirmation_sms",
            ],
        )
        return None
    if not bool(res):
        log.error(
            "Failed to schedule SMS for member appointment confirmation",
            appointment_id=appointment.id,
            exception_message=res.error_message,
        )
    else:
        stats.increment(
            metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["result:success", "notification_type:appointments"],
        )

    return res


@ddtrace.tracer.wrap()
@retryable_job("priority", retry_limit=3, team_ns="virtual_care")
def sms_notify_upcoming_appointments_practitioner() -> None:
    """
    Job that notifies pracititioners about upcoming appointments using SMS.
    """
    application_name = ROLES.practitioner

    # get upcoming appointments
    appointments = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start > datetime.datetime.utcnow(),
            Appointment.scheduled_start
            <= datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
            Appointment.cancelled_at == None,
        )
        .all()
    )

    if not appointments:
        log.info(
            f"No upcoming appointments that require notify action for {application_name}"
        )

    for appointment in appointments:
        if not appointment.state == APPOINTMENT_STATES.scheduled:
            log.info(
                f"Appointment {appointment.id} not scheduled - unable to notify for upcoming appointment"
            )
            continue

        # determine if the user was already notified
        notified = False
        push_key = _get_push_key(application_name)
        sms_key = _get_sms_key(application_name)
        keys = [push_key, sms_key]
        for notification_key in keys:
            if appointment.json.get(notification_key):
                log.info(
                    f"Already notified {application_name} for appointment {appointment.id}",
                    notification_key=notification_key,
                )
                notified = True
                break

        if notified:
            continue

        log.info(
            f"Attempting to send SMS to practitioner for upcoming appointment {appointment.id}",
            appointment_id=appointment.id,
        )

        # get profile
        profile: MemberProfile | PractitionerProfile
        user = appointment.practitioner
        profile = user.practitioner_profile
        user_role = user.role_name if profile else None
        if not profile:
            log.warning(
                "Unable to send SMS for upcoming appointment - profile unavailable",
                application_name=application_name,
                appointment_id=appointment.id,
                user_id=user.id,
                user_role=user_role,
            )

            stats.increment(
                metric_name=SMS_MISSING_PROFILE,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:success",
                    "notification_type:appointments",
                    f"user_role:{user_role}",
                    "source:sms_notify_upcoming_appointments_practitioner",
                ],
            )
            continue
        elif not profile.phone_number:
            log.warning(
                "Unable to send SMS for upcoming appointment - profile number unavailable",
                application_name=application_name,
                appointment_id=appointment.id,
                user_id=user.id,
                user_role=user_role,
            )

            stats.increment(
                metric_name=SMS_MISSING_PROFILE_NUMBER,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{user_role}",
                    "source:sms_notify_upcoming_appointments_practitioner",
                ],
            )
            continue

        # sms message
        message = f"Your next Maven appointment starts in {appointment._starts_in_minutes()} minutes! Make sure you have good WiFi."
        parsed_phone_number = parse_phone_number(profile.phone_number)
        # if we were unable to parse the phone number we adhere to the default condition of including the url
        if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
            deeplink = f"{current_app.config['BASE_URL']}/mp_/my-schedule"
            message = f"{message} Review appointment details here: {deeplink}"

        _send_sms_upcoming_appointment(
            appointment, profile, sms_key, application_name, message
        )


def _send_sms_upcoming_appointment(
    appointment: Appointment,
    profile: MemberProfile | PractitionerProfile,
    notification_key: str,
    application_name: str,
    message: str,
) -> None:
    """
    Sends an SMS message to either the member or the practitioner based on the application name
    for an upcoming appointment.
    """

    try:
        result = send_sms(
            message=message,
            to_phone_number=profile.phone_number,
            user_id=profile.user_id,
            notification_type="appointments",
            appointment_id=appointment.id,
        )
    except Exception as e:
        log.exception(
            "Exception found when attempting to send SMS notification for appointment",
            appointment_id=appointment.id,
            user_id=profile.user_id,
            exception=e,
        )

        stats.increment(
            metric_name=MAVEN_SMS_DELIVERY_ERROR,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:appointments",
                "reason:maven_server_exception",
                "source:_send_sms_upcoming_appointment",
            ],
        )
        return None
    if result.is_ok:
        log.info(
            "Sent SMS for upcoming appointment",
            application_name=application_name,
            appointment_id=appointment.id,
            user_id=profile.user_id,
        )
        stats.increment(
            metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["result:success", "notification_type:appointments"],
        )
        try:
            now = datetime.datetime.utcnow()
            appointment.json[notification_key] = now.isoformat()
            db.session.add(appointment)
            db.session.commit()
        except Exception as e:
            log.exception(
                f"Error updating appointment notification key for appointment {appointment.id}",
                application_name=application_name,
                notification_key=notification_key,
                exception=e,
            )
    else:
        log.info(
            f"Couldn't notify {application_name} via SMS for appointment {appointment.id}"
        )
        if result.is_blocked:
            log.info(f"User {profile.user_id} is sms blocked: {result.error_message}")
            db.session.add(profile)
            profile.mark_as_sms_blocked(result.error_code)
            db.session.commit()
        if result.error_code:
            log.error(
                f"Error sending SMS to {application_name} for appointment {appointment.id}",
                error_code=result.error_code,
                error_message=result.error_message or None,
            )


#     # *** Temporarily commenting out the code that will call code to send push notifications
#     # *** until we can investigate/find out what is happening with push notifications
# def push_notify_upcoming_appointment(
#     appointment_id: int, application_name: str
# ) -> bool:
#     """
#     Sends push notification to either the member or the practitioner based on the application name.
#     Sends push notification to the device they have registered with the application.

#     Returns: True if the push notification was sent successfully, otherwise False.
#     """
#     appointment = get_appointment(appointment_id)
#     if not appointment:
#         log.info(
#             f"No appointment for id {appointment_id} - unable to send push notification for upcoming appointment"
#         )
#         return False

#     if not appointment.state == APPOINTMENT_STATES.scheduled:
#         log.info(
#             f"Appointment {appointment.id} not scheduled - unable to notify for upcoming appointment"
#         )
#         return False

#     # determine if the user was already notified
#     if _notified(appointment, application_name):
#         return False

#     log.info(
#         f"Attempting to send push notification for upcoming appointment {appointment_id}",
#         application_name=application_name,
#     )

#     device_ids = _get_device_ids(appointment, application_name)
#     if not device_ids:
#         log.info(
#             f"No device ids for push notification for appointment {appointment_id}",
#             application_name=application_name,
#         )
#         return False

#     log.info(
#         f"Sending push notification to {len(device_ids)} devices for appointment {appointment_id}",
#         application_name=application_name,
#     )

#     try:
#         link = f"maven://appointment/{appointment.api_id}"
#         result = apns_send_bulk_message(
#             device_ids,
#             (
#                 f"Your Maven appointment begins in {appointment._starts_in_minutes()} minutes!"
#             ),
#             sound="default",
#             application_name=application_name,
#             extra={"link": link},
#         )

#         # Potentially refactor this later when metrics are implemented
#         # Consider checking for specific error codes, reason, explanation, why tokens failed, etc.
#         # Could also determine if tokens should be retried and specifically which tokens should be retried.
#         if not result or (
#             result and (result.errors or result.failed or result.needs_retry())
#         ):
#             log.error(
#                 f"Failed to send push notification for upcoming appointment {appointment_id}",
#                 application_name=application_name,
#             )
#             return False
#     except Exception as e:
#         log.exception(
#             f"Error sending push notification for upcoming appointment {appointment_id}",
#             application_name=application_name,
#             exception=e,
#         )
#         return False

#     log.info(
#         f"Sent push notification for upcoming appointment {appointment.id}",
#         application_name=application_name,
#     )

#     notification_key = _get_push_key(application_name)
#     _update_appointment_notification_key(
#         appointment, notification_key, application_name
#     )

#     return True


#     # *** Temporarily commenting out the code that will call code to send push notifications
#     # *** until we can investigate/find out what is happening with push notifications
# def _get_device_ids(appointment: Appointment, application_name: str) -> Iterable[str]:
#     """
#     Gets the device ids/tokens associated with the appointment and the application name (practitioner, member).
#     """
#     device_ids = []
#     if not appointment:
#         return device_ids

#     for device in Device.for_user(
#         getattr(appointment, application_name), application_name
#     ):
#         device_ids.append(device.device_id)

#     return device_ids


def _get_sms_key(application_name: str) -> str:
    return f"notified:sms:{application_name}"


def _get_push_key(application_name: str) -> str:
    return f"notified:{application_name}"


@job("priority", traced_parameters=("appointment_id",))
def send_member_cancellation_note(appointment_id, note=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug("Going to send_member_cancellation_note")
    appointment: Appointment = get_appointment(appointment_id)
    if appointment:
        braze_events.appointment_canceled_prac_to_member(appointment, note)
        user = appointment.member
        user_id = appointment.member.id
        mp = user.member_profile

        if not mp:
            log.warning(
                "Unable to send SMS for cancelled appointment - profile unavailable",
                appointment_id=appointment.id,
                user_id=user_id,
                user_role=ROLES.member,
            )
            stats.increment(
                metric_name=SMS_MISSING_PROFILE,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.member}",
                    "source:send_member_cancellation_note",
                ],
            )
            return None
        if mp.phone_number:
            if not appointment.practitioner:
                raise ValueError(f"Appointment {appointment.id} has no practitioner")
            message = message_with_enforced_locale(
                user=appointment.member, text_key="member_cancellation_note"
            ).format(name=appointment.practitioner.first_name)

            try:
                result = send_sms(
                    message=message,
                    to_phone_number=mp.phone_number,
                    user_id=mp.user_id,
                    notification_type="appointments",
                    appointment_id=appointment_id,
                )
            except Exception as e:
                log.exception(
                    "Exception found when attempting to send SMS notification for appointment",
                    appointment_id=appointment_id,
                    user_id=mp.user_id,
                    exception=e,
                )

                stats.increment(
                    metric_name=MAVEN_SMS_DELIVERY_ERROR,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=[
                        "result:failure",
                        "notification_type:appointments",
                        "reason:maven_server_exception",
                        "source:send_member_cancellation_note",
                    ],
                )

                return None
            if result.is_ok:
                log.info(
                    "Appointment cancellation SMS alert to member is sent to member profile",
                    appointment_id=appointment_id,
                    user_id=mp.user_id,
                )
                stats.increment(
                    metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=["result:success", "notification_type:appointments"],
                )
            else:
                log.info(
                    "Couldn't notify member via SMS for appointment cancellation",
                    appointment_id=appointment_id,
                    user_id=mp.user_id,
                )
                if result.is_blocked:
                    db.session.add(mp)
                    mp.mark_as_sms_blocked(result.error_code)
                    log.warn(
                        "Member Profile has a phone number that is sms blocked",
                        error_message=result.error_message,
                        user_id=mp.user_id,
                    )
        else:
            log.warning(
                "Unable to send SMS for cancelled appointment - profile number unavailable",
                appointment_id=appointment.id,
                user_id=user_id,
            )

            stats.increment(
                metric_name=SMS_MISSING_PROFILE_NUMBER,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.member}",
                    "source:send_member_cancellation_note",
                ],
            )
            _send_push_cancellation(appointment, "member")


@job("priority", traced_parameters=("appointment_id",))
def send_practitioner_cancellation_note(appointment_id, payment_amount=0, note=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    appointment = get_appointment(appointment_id)
    if appointment:
        braze_events.appointment_canceled_member_to_member(appointment)
        braze_events.appointment_canceled_member_to_practitioner(
            appointment, payment_amount, note
        )
        user = appointment.practitioner
        pp = user.practitioner_profile
        if not pp:
            log.warning(
                "Unable to send SMS for cancelled appointment - profile unavailable",
                appointment_id=appointment.id,
                user_id=user.id,
                user_role=ROLES.practitioner,
            )

            stats.increment(
                metric_name=SMS_MISSING_PROFILE,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.practitioner}",
                    "source:send_practitioner_cancellation_note",
                ],
            )
            return None
        # DO NOT send SMS or Push notifications to CAs
        if not pp.is_cx:
            _send_push_cancellation(appointment, "practitioner")

            # Practitioner SMS notification
            member_name = (
                "An anonymous user" if appointment.is_anonymous else "A Maven member"
            )
            message = f"{member_name} cancelled an appointment on Maven!"

            if not pp.phone_number:
                log.warning(
                    "Unable to send SMS for cancelled appointment - profile number unavailable",
                    appointment_id=appointment.id,
                    user_id=user.id,
                    user_role=ROLES.practitioner,
                )

                stats.increment(
                    metric_name=SMS_MISSING_PROFILE_NUMBER,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=[
                        "result:failure",
                        "notification_type:appointments",
                        f"user_role:{ROLES.practitioner}",
                        "source:send_practitioner_cancellation_note",
                    ],
                )
                return None
            try:
                result = send_sms(
                    message=message,
                    to_phone_number=pp.phone_number,
                    user_id=pp.user_id,
                    notification_type="appointments",
                    appointment_id=appointment_id,
                )
            except Exception as e:
                log.exception(
                    "Exception found when attempting to send SMS notification for appointment",
                    appointment_id=appointment_id,
                    user_id=pp.user_id,
                    exception=e,
                )

                stats.increment(
                    metric_name=MAVEN_SMS_DELIVERY_ERROR,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=[
                        "result:failure",
                        "notification_type:appointments",
                        "reason:maven_server_exception",
                        "source:send_practitioner_cancellation_note",
                    ],
                )

                return None
            if result.is_ok:
                log.info(
                    "Sent Practitioner Profile User an SMS for appointment",
                    appointment_id=appointment_id,
                    user_id=pp.user_id,
                )
                stats.increment(
                    metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=["result:success", "notification_type:appointments"],
                )
            else:
                log.info(
                    f"Couldn't notify practitioner via SMS for appointment: ({appointment.id})"
                )
                if result.is_blocked:
                    db.session.add(pp)
                    pp.mark_as_sms_blocked(result.error_code)
                    log.warn(
                        "Practitioner Profile User phone number is sms blocked",
                        error_message=result.error_message,
                        user_id=pp.user_id,
                    )


def _send_push_cancellation(appointment, application_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if application_name == ROLES.practitioner:
        # send anonymized name to practitioner if needed
        canceller_name = appointment.member_name
    elif application_name == ROLES.member:
        # we are sending practitioner name to the member
        canceller_name = appointment.practitioner.full_name
    else:
        log.warning(
            "Unsupported name for appointment.", application_name=application_name
        )
        return

    device_ids = []
    for device in Device.for_user(
        getattr(appointment, application_name), application_name
    ):
        device_ids.append(device.device_id)

    if not device_ids:
        log.info(
            "No device IDs to notify for cancelled appointment: (%s)", appointment.id
        )
        return

    try:
        apns_send_bulk_message(
            device_ids,
            f"{canceller_name} cancelled your upcoming appointment!",
            application_name=application_name,
            extra={"link": f"maven://appointment/{appointment.api_id}"},
        )
    except Exception as e:
        log.exception(
            "Problem sending notification via APNS.", device_ids=device_ids, exception=e
        )


@job("priority", traced_parameters=("appointment_id",))
def notify_rx_info_entered(appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Let the practitioner know Rx info is entered.
    """
    noti_key = "notified:practitioner_rx_added"
    appointment = get_appointment(appointment_id)
    if appointment:
        if appointment.state not in (
            APPOINTMENT_STATES.completed,
            APPOINTMENT_STATES.payment_pending,
            APPOINTMENT_STATES.payment_resolved,
        ):
            log.info(
                (
                    "Not notifying practitioner about RX info added for appointment: (%s) - "
                    "not completed yet."
                ),
                appointment.id,
            )
            return

        if appointment.json.get(noti_key):
            log.debug(
                "Already notified practitioner rx added for appointment: (%s)",
                appointment.id,
            )
            return

        log.debug(
            "Going to notify practitioner: (%s) about RX info added for appointment: (%s)",
            appointment.practitioner.id,
            appointment.id,
        )

        user = appointment.practitioner
        profile = user.practitioner_profile

        if not profile:
            log.warning(
                "Unable to send SMS for RX info added - profile unavailable",
                appointment_id=appointment.id,
                user_id=appointment.member.id,
                user_role=ROLES.practitioner,
            )
            stats.increment(
                metric_name=SMS_MISSING_PROFILE,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.practitioner}",
                    "source:notify_rx_info_entered",
                ],
            )
            return
        elif not profile.phone_number:
            log.warning(
                "Unable to send SMS for RX info added - profile number unavailable",
                appointment_id=appointment.id,
                user_id=user.id,
            )

            stats.increment(
                metric_name=SMS_MISSING_PROFILE_NUMBER,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    f"user_role:{ROLES.practitioner}",
                    "source:notify_rx_info_entered",
                ],
            )
            return

        try:
            result = send_sms(
                message="A Maven Member has added their pharmacy on Maven.",
                to_phone_number=profile.phone_number,
                user_id=profile.user_id,
                notification_type="appointments",
                appointment_id=appointment_id,
            )
        except Exception as e:
            log.exception(
                "Exception found when attempting to send SMS notification for RX info added for appointment",
                appointment_id=appointment_id,
                user_id=profile.user_id,
                exception=e,
            )

            stats.increment(
                metric_name=MAVEN_SMS_DELIVERY_ERROR,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:appointments",
                    "reason:maven_server_exception",
                    "source:notify_rx_info_entered",
                ],
            )
            return None
        if result.is_ok:
            log.info(
                "Sent SMS Notification to Practitioner about RX info added for appointment",
                user_id=profile.user_id,
            )
            stats.increment(
                metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=["result:success", "notification_type:appointments"],
            )
        if result.is_blocked:
            log.debug(
                "Practitioner Profile: (%s) has a phone number that is sms blocked: %s",
                profile.user_id,
                result.error_message,
            )
            db.session.add(profile)
            profile.mark_as_sms_blocked(result.error_code)

        braze_events.user_added_pharmacy(
            appointment.practitioner, appointment.member_name
        )

        now = datetime.datetime.utcnow()
        appointment.json[noti_key] = now.isoformat()
        db.session.add(appointment)
        db.session.commit()


# Deprecate this method and use send_slack_cancellation() in
# appointments/services/v2/notification.py instead
def send_slack_cancellation(appointment: Appointment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not appointment or not appointment.practitioner:
        raise ValueError("No appointment or practitioner provided")

    profile = appointment.practitioner.practitioner_profile
    phone_no = profile.phone_number

    practitioner_info = "%s [%s]%s" % (
        appointment.practitioner.full_name,
        appointment.practitioner.email,
        f" ({phone_no})" if phone_no else "",
    )
    internal_string = (
        "Internal"
        if appointment.member.email.endswith("mavenclinic.com")
        else "External"
    )
    admin_link = f"https://admin.production.mvnctl.net:444/admin/appointment/edit/?id={appointment.id}"
    member_or_practitioner = (
        "member"
        if appointment.cancelled_by_user_id == appointment.member.id
        else "practitioner"
    )

    tmpl = (
        "CANCELLED - ID: <%s|%s>. Scheduled start was in %s "
        " w/ %s - Booking was %s. Cancelled by %s."
    )
    message = tmpl % (
        admin_link,
        appointment.id,
        appointment.starts_in(),
        practitioner_info,
        internal_string,
        member_or_practitioner,
    )
    notify_bookings_channel(message)

    track_svc = tracks_svc.TrackSelectionService()

    if track_svc.is_enterprise(user_id=appointment.member.id):
        notify_enterprise_bookings_channel(message)
        vip_title = "VIP Appointment Cancellation"
        notify_vip_bookings(appointment.member, vip_title, message)


@job("priority")
def handle_push_notifications_for_1_hour_reminder() -> None:
    """
    Trigger 1 hour upcoming appointment reminder braze event for appointments that received SMS reminders for a 3-hour
     upcoming appointment
    :return:
    """
    now = datetime.datetime.utcnow()
    buffer_minutes = APPOINTMENT_NOTIFICATION_REMINDER_BUFFER

    # calculate the reminder window with a buffer; give a 10 minute buffer so the cron has 1 chance to miss
    p50 = now + datetime.timedelta(minutes=60 - buffer_minutes)
    p60 = now + datetime.timedelta(minutes=60)

    notified_appts = (
        db.session.query(Appointment)
        .filter(
            Appointment.scheduled_start.between(p50, p60),
            Appointment.cancelled_at.is_(None),
            Appointment.json.contains("notified_180m_sms"),
        )
        .all()
    )

    for appt in notified_appts:
        if "notified_60m_push" not in appt.json:
            braze_events.appointment_reminder_member(
                appointment=appt, event_name=BRAZE_UPCOMING_APPT_REMINDER_1H
            )
            appt.json["notified_60m_push"] = True
            db.session.add(appt)
    db.session.commit()


@job("priority")
def remind_booking_series() -> None:
    """
    Runs every 5 minutes to alert people via text on how to launch appointment
    """
    sms_notify_how_to_launch.delay(team_ns="virtual_care")


@job("priority")
def sms_notify_how_to_launch() -> None:
    now = datetime.datetime.utcnow()

    kill_switch_enabled = feature_flags.bool_variation(
        flag_key="kill-switch-sms-notify-how-to-launch",
        default=False,
    )

    if kill_switch_enabled:
        # evaluate the feature flag value
        reminder_minutes_before_start = feature_flags.int_variation(
            APPOINTMENT_NOTIFICATIONS.SET_REMINDER_MINUTES_BEFORE_START,
            default=APPOINTMENT_NOTIFICATION_REMINDER_TIME_DEFAULT,
        )

        # calculate the reminder window with a buffer; give a 10 minute buffer so the cron has 1 chance to miss
        # (job runs every 5 mins)
        buffer_minutes = APPOINTMENT_NOTIFICATION_REMINDER_BUFFER
        p50 = now + datetime.timedelta(
            minutes=reminder_minutes_before_start - buffer_minutes
        )
        p60 = now + datetime.timedelta(minutes=reminder_minutes_before_start)

        how_to_launch_appts = (
            db.session.query(Appointment)
            .filter(
                Appointment.scheduled_start.between(p50, p60),
                Appointment.cancelled_at.is_(None),
            )
            .all()
        )
        log.debug(
            "Got %s appts to be sms notified about how to launch appt.",
            len(how_to_launch_appts),
        )
        appt: Appointment
        for appt in how_to_launch_appts:
            # check if any notification key exists in the json field - this means that the member has already been SMS notified
            existing_notifications = [
                key
                for key in appt.json.keys()
                if key.startswith("notified_") and key.endswith("_sms")
            ]
            if existing_notifications:
                log.info(
                    "Skipping appointment as it has already been SMS notified",
                    appointment_id=appt.id,
                )
                continue

            notification_key = f"notified_{reminder_minutes_before_start}m_sms"
            # If the upcoming reminder for a specific start time window has already been sent, do not send the reminder SMS
            # TODO: follow up to remove this code once appointments that don't have the new keys are already launched or overdue
            if appt.json and appt.json.get("notified:sms:how_to_launch"):
                continue

            # only send a braze event to notify the member when their appointment starts in 1 hour
            if reminder_minutes_before_start == 60:
                braze_events.appointment_reminder_member(
                    appointment=appt, event_name=BRAZE_UPCOMING_APPT_REMINDER_1H
                )
                appt.json["notified_60m_push"] = True

            user = appt.member
            profile = user.member_profile

            if not profile:
                log.warning(
                    "Unable to send SMS for upcoming appointment - profile unavailable",
                    appointment_id=appt.id,
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
                        "source:sms_notify_how_to_launch",
                    ],
                )
                continue

            elif not profile.phone_number:
                log.warning(
                    "Unable to send SMS for upcoming appointment - profile number unavailable",
                    appointment_id=appt.id,
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
                        "source:sms_notify_how_to_launch",
                    ],
                )
                continue

            phone_number = profile.phone_number
            parsed_phone_number = parse_phone_number(phone_number)

            # convert start time to a human-readable string to append to notification message
            start_time_msg = convert_time_to_message_str(
                upcoming_appt_time_in_mins=reminder_minutes_before_start
            )
            message = message_with_enforced_locale(
                user, "how_to_launch_notif_new_path"
            ).format(start_time=start_time_msg)

            # if we were unable to parse the phone number we adhere to the default condition of including the url
            if not parsed_phone_number or country_accepts_url_in_sms(
                parsed_phone_number
            ):
                cta_link = message_with_enforced_locale(
                    user=user, text_key="cta_how_to_launch_link"
                ).format(url=f"{current_app.config['BASE_URL']}/my-appointments")

                # ensure proper punctuation handling
                if message.endswith("."):
                    message = message[:-1]

                message = f"{message} {cta_link}"
            try:
                result = send_sms(
                    message=message,
                    to_phone_number=profile.phone_number,
                    user_id=profile.user_id,
                    notification_type="appointments",
                    appointment_id=appt.id,
                )
            except Exception as e:
                log.exception(
                    "Exception found when attempting to send SMS notification for appointment",
                    appointment_id=appt.id,
                    user_id=profile.user_id,
                    exception=e,
                )

                stats.increment(
                    metric_name=MAVEN_SMS_DELIVERY_ERROR,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=[
                        "result:failure",
                        "notification_type:appointments",
                        "reason:maven_server_exception",
                        "source:sms_notify_how_to_launch",
                    ],
                )
                continue
            if result.is_ok:
                log.info(
                    "Sent how to launch appointment instructions via SMS to Member profile",
                    user_id=profile.user_id,
                )
                stats.increment(
                    metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=["result:success", "notification_type:appointments"],
                )
            elif result.is_blocked:
                log.warn(
                    "Member Profile has a phone number that is sms blocked",
                    user_id=profile.user_id,
                    error_message=result.error_message,
                )
                db.session.add(profile)
                profile.mark_as_sms_blocked(result.error_code)

            if not appt.json:
                appt.json = {}

            appt.json["notified:sms:how_to_launch"] = now.isoformat()
            appt.json[notification_key] = now.isoformat()
            db.session.add(appt)
            db.session.commit()
    else:
        # give a 10 minute buffer so the cron has 1 chance to miss
        # (runs every 5 mins)
        p50 = now + datetime.timedelta(minutes=50)
        p60 = now + datetime.timedelta(minutes=60)

        how_to_launch_appts = (
            db.session.query(Appointment)
            .filter(
                Appointment.scheduled_start.between(p50, p60),
                Appointment.cancelled_at.is_(None),
            )
            .all()
        )
        log.debug(
            "Got %s appts to be sms notified about how to launch appt.",
            len(how_to_launch_appts),
        )
        appointment: Appointment
        for appointment in how_to_launch_appts:
            # If the appointment_meets_pilot_criteria function returns true and the member has an appointment ack, do not send the reminder SMS
            # https://mavenclinic.atlassian.net/browse/VIRC-1176
            if (
                appointment.json and appointment.json.get("notified:sms:how_to_launch")
            ) or (
                appointment_meets_pilot_criteria(appointment)
                and MemberAppointmentAck.query.filter(
                    MemberAppointmentAck.appointment_id == appointment.id
                ).one_or_none()
            ):
                continue

            # send a braze event to notify the member about an upcoming appointment
            braze_events.appointment_reminder_member(
                appointment=appointment, event_name=BRAZE_UPCOMING_APPT_REMINDER_1H
            )

            user = appointment.member
            profile = user.member_profile

            if not profile:
                log.warning(
                    "Unable to send SMS for upcoming appointment - profile unavailable",
                    appointment_id=appointment.id,
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
                        "source:sms_notify_how_to_launch",
                    ],
                )
                continue

            elif not profile.phone_number:
                log.warning(
                    "Unable to send SMS for upcoming appointment - profile number unavailable",
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
                        "source:sms_notify_how_to_launch",
                    ],
                )
                continue
            message = message_with_enforced_locale(
                user=user, text_key="how_to_launch_notif_old_path"
            )
            try:
                result = send_sms(
                    message=message,
                    to_phone_number=profile.phone_number,
                    user_id=profile.user_id,
                    notification_type="appointments",
                    appointment_id=appointment.id,
                )
            except Exception as e:
                log.exception(
                    "Exception found when attempting to send SMS notification for appointment",
                    appointment_id=appointment.id,
                    user_id=profile.user_id,
                    exception=e,
                )

                stats.increment(
                    metric_name=MAVEN_SMS_DELIVERY_ERROR,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=[
                        "result:failure",
                        "notification_type:appointments",
                        "reason:maven_server_exception",
                        "source:sms_notify_how_to_launch",
                    ],
                )
                continue
            if result.is_ok:
                log.info(
                    "Sent how to launch appointment instructions via SMS to Member profile",
                    user_id=profile.user_id,
                )
                stats.increment(
                    metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=["result:success", "notification_type:appointments"],
                )
            elif result.is_blocked:
                log.warn(
                    "Member Profile has a phone number that is sms blocked",
                    user_id=profile.user_id,
                    error_message=result.error_message,
                )
                db.session.add(profile)
                profile.mark_as_sms_blocked(result.error_code)

            if not appointment.json:
                appointment.json = {}

            appointment.json["notified:sms:how_to_launch"] = now.isoformat()
            db.session.add(appointment)
            db.session.commit()


# TODO: refactor to only pass in the member_id instead
def notify_vip_bookings(member, title, message) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    track_svc = tracks_svc.TrackSelectionService()
    organization = track_svc.get_organization_for_user(user_id=member.id)

    if not track_svc.is_enterprise(user_id=member.id):
        return

    if not organization:
        log.warning("Missing organization", user_id=member.id)
        return

    if not organization.name:
        log.warning("Missing organization name", user_id=member.id)
        return

    if organization.name.lower() == BOOKINGS_ENTERPRISE_VIP_ORGANIZATION.lower():
        notify_vip_bookings_channel(title, message)


@job()
@ddtrace.tracer.wrap()
def schedule_member_confirm_appointment_sms() -> None:
    """
    Find all of the MemberAppointmentAcks with Appointments that start in 7 days or less and schedule a confirmtation SMS in Twilio

    Twilio restricts how long out a message can be scheduled (7 days) but Maven allows for scheduling appointments further in advance.
    """
    acks = _get_acks_for_confirmation()
    for ack in acks:
        try:
            res = schedule_member_appointment_confirmation_sms(
                ack.phone_number, ack.appointment, ack.user_id
            )
            if bool(res):
                ack.confirm_message_sid = res._result.sid
                ack.is_acked = False
                db.session.add(ack)
                db.session.commit()
        except Exception as e:
            log.error(
                "An arror occurred scheduling a member appointment ack sms message",
                appointment_id=ack.appointment_id,
                exception=e,
            )

    acks_again = _get_acks_for_confirmation()
    if len(acks_again) != 0:
        stats.gauge(
            metric_name="appointment_notifications.schedule_member_confirm_appointment_sms.overdue_member_ack_sms",
            pod_name=stats.PodNames.VIRTUAL_CARE,
            metric_value=len(acks_again),
        )


def _get_acks_for_confirmation() -> list[MemberAppointmentAck]:
    """
    Get a list of MemberAppointmentAcks that need to schedule a confirmation SMS
    """
    return (
        MemberAppointmentAck.query.join(Appointment)
        .filter(
            MemberAppointmentAck.confirm_message_sid == None,
            Appointment.scheduled_start
            <= datetime.datetime.utcnow() + datetime.timedelta(days=7),
        )
        .order_by(Appointment.scheduled_start.asc())
        .all()
    )


@retryable_job("priority", retry_limit=3, team_ns="virtual_care")
def cancel_member_appointment_confirmation(appointment_id: int) -> None:
    """
    Cancels the confirmation message for confirming an appointment to a member and deletes the MemberAppointmentAck.

    When an appointment is cancelled and there has not been an attempt to confirm with the member, we do not want to notify them about the cancelled appointment.
    If we have already send the confirmation SMS to the member, the MemberAppointmentAck will not be deleted.

    If the SMS has yet to be scheduled, there will not be a call to cancel the delivery of the message as it does not exist.
    """
    # Finds ack for appointment where the confirmation message has not been sent
    ack_to_cancel = MemberAppointmentAck.query.filter(
        MemberAppointmentAck.appointment_id == appointment_id,
        MemberAppointmentAck.sms_sent_at == None,
    ).one_or_none()
    if ack_to_cancel:
        # Only cancels SMS that has an sid, its possible that the SMS has yet to be scheduled
        if ack_to_cancel.confirm_message_sid is not None:
            cancel_sms(ack_to_cancel.confirm_message_sid)
        # Remove the ack from the database
        db.session.delete(ack_to_cancel)
        db.session.commit()
