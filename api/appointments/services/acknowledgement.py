from __future__ import annotations

import datetime
from typing import Optional

import ddtrace

from appointments.models.appointment import Appointment
from appointments.models.member_appointment import MemberAppointmentAck
from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.tasks.appointment_notifications import notify_vip_bookings
from authn.models.user import User
from l10n.utils import message_with_enforced_locale
from models.profiles import MemberProfile
from storage.connection import db
from utils.data import normalize_phone_number
from utils.log import logger
from utils.slack import notify_bookings_channel, notify_enterprise_bookings_channel

# Responses that we treat as a confirmation (case insensitive)
CONFIRM_ACK_RESPONSES = ["yes", "y"]

log = logger(__name__)


@ddtrace.tracer.wrap()
def acknowledge_appointment_by_phone_number(
    phone_number: str, message_sid: str, body: str
) -> Optional[str]:
    """
    Acknowledge appointments by the phone number replying to an SMS. Can be either a Practitioner or Member.

    Returns the reply message to send back to the responder
    """
    reply = _acknowledge_appointment_for_practitioner(
        phone_number, message_sid, body=body
    )
    if not reply:
        reply = _acknowledge_appointment_for_member(phone_number, message_sid, body)
    return reply


@ddtrace.tracer.wrap()
def _acknowledge_appointment_for_practitioner(
    phone_number: str, message_sid: str, body: str
) -> Optional[str]:
    """
    Finds any PractitionerAppointmentAck records that have not been ack'd by the provided phone_number and acks them.
    """
    incoming_phone_number, _ = normalize_phone_number(phone_number, None)
    acks_to_mark = (
        db.session.query(PractitionerAppointmentAck)
        .filter(
            PractitionerAppointmentAck.phone_number == incoming_phone_number,
            PractitionerAppointmentAck.is_acked == False,
            PractitionerAppointmentAck.ack_by > datetime.datetime.utcnow(),
        )
        .all()
    )
    if not acks_to_mark:
        return None

    if body.lower() not in CONFIRM_ACK_RESPONSES:
        return "For help rebooking or other questions, please email providersupport@mavenclinic.com."

    log.info("Acknowledging appointment for practitioner: %s", acks_to_mark)

    for ack in acks_to_mark:
        ack.is_acked = True
        db.session.add(ack)
        db.session.commit()
        log.debug("Acknowledged %s", ack)

    message = f"Reply from {incoming_phone_number}: {body}"
    notify_bookings_channel(message)
    for ack in acks_to_mark:
        if ack.appointment.member.is_enterprise:
            notify_enterprise_bookings_channel(message)
            vip_title = "New VIP appointment confirmed"
            notify_vip_bookings(ack.appointment.member, vip_title, message)

    return "Thank you for confirming this appointment. If you have any questions, email providersupport@mavenclinic.com."


@ddtrace.tracer.wrap()
def _acknowledge_appointment_for_member(
    phone_number: str, message_sid: str, body: str
) -> str | None:
    """
    Finds a MemberAppointmentAck record that have not been ack'd by the provided phone_number for an Appointment that has yet to begin and ack's it.
    """
    incoming_phone_number, _ = normalize_phone_number(phone_number, None)
    ack_to_mark = (
        db.session.query(MemberAppointmentAck)
        .join(Appointment)
        .filter(
            MemberAppointmentAck.phone_number == incoming_phone_number,
            MemberAppointmentAck.is_acked == False,
            Appointment.scheduled_start > datetime.datetime.utcnow(),
        )
        .order_by(Appointment.scheduled_start.asc())
        .first()
    )
    if not ack_to_mark:
        return None

    matching_profiles = (
        db.session.query(User)
        .join(MemberProfile)
        .filter(
            MemberProfile.phone_number == incoming_phone_number,
            MemberProfile.user_id == User.id,
        )
        .order_by(MemberProfile.created_at.desc())
        .all()
    )

    if matching_profiles:
        if len(matching_profiles) > 1:
            matching_profile_ids = [profile.id for profile in matching_profiles]
            log.warning(
                "Multiple results found for user id and phone number. Returning the most recent result.",
                matching_profile_ids=matching_profile_ids,
            )

        # use the most recent user profile
        user = matching_profiles[0]
    else:
        log.warning("Could not find matching profile for given number")
        return None

    if body.lower() in CONFIRM_ACK_RESPONSES:
        ack_to_mark.is_acked = True
        ack_to_mark.ack_date = datetime.datetime.utcnow()
        ack_to_mark.reply_message_sid = message_sid
        db.session.add(ack_to_mark)
        db.session.commit()
        log.debug("Acked %s", ack_to_mark)

        return message_with_enforced_locale(
            user=user, text_key="member_confirm_response"
        )
    else:
        return message_with_enforced_locale(
            user=user, text_key="member_confirm_invalid_response"
        )


def update_member_appointment_ack_sent(message_sid: str) -> None:
    """
    Sets the sms_sent_at when the message is sent. This is called from the status callback that Twilio calls when a message status change occurrs.
    """
    ack = (
        db.session.query(MemberAppointmentAck)
        .filter(MemberAppointmentAck.confirm_message_sid == message_sid)
        .one_or_none()
    )
    if ack:
        ack.sms_sent_at = datetime.datetime.utcnow()
        db.session.add(ack)
        db.session.commit()
