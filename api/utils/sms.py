from __future__ import annotations

import datetime
from typing import Iterable

import ddtrace
import phonenumbers
from marshmallow_v1 import ValidationError
from phonenumbers.phonenumberutil import region_code_for_country_code

import messaging.services.twilio as twilio
from common import stats
from models.phone import BlockedPhoneNumber
from models.profiles import MemberProfile
from utils.data import normalize_phone_number
from utils.log import logger

log = logger(__name__)

# India, Malaysia, Taiwan, Denmark and Brazil do not allow SMS to contain urls
COUNTRIES_WHERE_SMS_CANT_CONTAIN_URL = ["IN", "MY", "TW", "DK", "BR"]


def parse_phone_number(
    phone_number: str | None = None,
) -> phonenumbers.PhoneNumber | None:
    try:
        return phonenumbers.parse(phone_number)
    except Exception as e:
        log.warn("Problem parsing phone number.", exception=str(e))
        return None


def country_accepts_url_in_sms(pn: phonenumbers.PhoneNumber | None) -> bool:
    if not pn:
        return True
    phone_country = region_code_for_country_code(pn.country_code)
    if phone_country in COUNTRIES_WHERE_SMS_CANT_CONTAIN_URL:
        return False
    return True


def format_phone_number(to_phone_number):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Format a phone number with error handling and stat tracing
    """
    try:
        with ddtrace.tracer.trace("sms.phone_number_validation"):
            return normalize_phone_number(to_phone_number, None)
    except ValidationError as ve:
        log.warn("Phone number failed normalization.", error_message=str(ve))
        raise ve


def send_sms(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    message: str,
    to_phone_number: str | None,
    user_id: int | None = None,
    *,
    send_at: datetime.datetime | None = None,
    pod: stats.PodNames = stats.PodNames.VIRTUAL_CARE,
    metrics_tags: Iterable[str] = (),
    notification_type: str | None = None,
    appointment_id: int | None = None,
    **context,
):
    if not to_phone_number:
        log.warn("SMS NOT sent due to the absence of the phone.", user_id=user_id)
        stats.increment(
            "sms.null_phone_number",
            pod_name=pod,
            tags=[*metrics_tags],
        )
        return twilio.SMSDeliveryResult(None)

    try:
        to_normalized, to_parsed = format_phone_number(to_phone_number)
    except ValidationError as ve:
        log.warn(
            "SMS NOT sent due to inability to normalize phone number.",
            user_id=user_id,
            error_message=str(ve),
            **context,
        )
        return twilio.SMSDeliveryResult(None, is_ok=False, is_blocked=True)

    bpn = BlockedPhoneNumber.query.filter(
        BlockedPhoneNumber.digits == to_normalized
    ).first()
    if bpn:
        log.warn(
            "SMS NOT sent because phone number is blocked.",
            error_code=bpn.error_code,
            user_id=user_id,
            **context,
        )
        stats.increment("sms.blocked_phone_number", pod_name=pod, tags=[*metrics_tags])
        return twilio.SMSDeliveryResult(
            None, is_ok=False, is_blocked=True, error_code=bpn.error_code
        )

    to_e164 = phonenumbers.format_number(to_parsed, phonenumbers.PhoneNumberFormat.E164)

    return twilio.send_message(
        to=to_e164,
        message=message,
        pod=stats.PodNames.VIRTUAL_CARE,
        send_at=send_at,
        notification_type=notification_type,
        appointment_id=appointment_id,
    )


def permanently_delete_messages_for_user(user_id: str) -> bool:
    """
    Deletes all messages related to a user
    Returns True if all messages were deleted
    """
    log.debug("Permanently deleting SMS data for user (%s)", user_id)

    member_profile = MemberProfile.query.get(user_id)
    if member_profile is None:
        log.warn(
            "Could not delete SMS data for user (%s). No member profile exists.",
            user_id,
        )
        return False
    if not member_profile.phone_number:
        log.info(
            "Could not delete SMS data for user (%s). No phone_number exists on profile.",
            user_id,
        )
        return False
    try:
        _, to_parsed = format_phone_number(member_profile.phone_number)
    except ValidationError as ve:
        log.error(
            "SMS Data not deleted due to inability to normalize phone number.",
            error_message=str(ve),
        )
        return False

    to_e164 = phonenumbers.format_number(to_parsed, phonenumbers.PhoneNumberFormat.E164)

    result = twilio.delete_messages(to_e164, stats.PodNames.MPRACTICE_CORE)

    log.debug("Messages deleted for user (%s)", user_id)

    return result


def cancel_sms(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    sid: str,
    *,
    pod: str = stats.PodNames.TEST_POD,
    metrics_tags: Iterable[str] = (),
):
    """
    Cancels a scheduled SMS message
    """
    return twilio.cancel_message(sid, pod=pod, metrics_tags=metrics_tags)
