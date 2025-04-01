from __future__ import annotations

import datetime
import os
from typing import Iterable

import ddtrace
from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.rest import Client

from common import stats
from common.constants import Environment
from utils.log import logger

log = logger(__name__)

TWILIO_MESSAGING_SERVICE_SID = os.environ.get("TWILIO_MESSAGING_SERVICE_SID")


# define the URL mapping for the status callback
url_mapping = {
    Environment.QA1: "https://www.qa1.mvnapp.net/api/v1/vendor/twilio/message_status",
    Environment.QA2: "https://www.qa2.mvnapp.net/api/v1/vendor/twilio/message_status",
    Environment.PRODUCTION: "https://www.mavenclinic.com/api/v1/vendor/twilio/message_status",
    Environment.STAGING: "https://www.staging.mvnapp.net/api/v1/vendor/twilio/message_status",
}

# get the current environment
current_env = Environment.current()

# get the status callback URL based on the current Environment
status_callback_url = url_mapping.get(current_env)

try:
    twilio_client = Client(
        username=os.environ["TWILIO_ACCOUNT_SID"],
        password=os.environ["TWILIO_AUTH_TOKEN"],
    )
except Exception as e:
    log.warning("Twilio initialization error: %s", e)
    twilio_client = None

# https://www.twilio.com/docs/api/errors
BLOCKED_ERROR_CODES = (21610, 21612, 32203)


class SMSDeliveryResult:
    def __init__(self, sms_result, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Wrapper for Twilio SMS delivery result
        :param sms_result: twilio.rest.api.v2010.account.message.MessageInstance or None
        :param kwargs: params to override delivery result when result is None
        """
        self._result = sms_result

        self.to = kwargs.get("to")
        self.error_code = kwargs.get("error_code")
        self.error_message = kwargs.get("error_message")
        self.is_ok = bool(kwargs.get("is_ok"))
        self.is_blocked = bool(kwargs.get("is_blocked"))
        self.appointment_id = kwargs.get("appointment_id")

        if self._result:
            self.to = self._result.to
            self.error_code = self._result.error_code
            self.error_message = self._result.error_message
            # https://support.twilio.com/hc/en-us/articles/223134347
            if self._result.status not in ("failed", "undelivered"):
                log.info(
                    "SMS message sent",
                    status=self._result.status,
                    sid=self._result.sid,
                    appointment_id=self.appointment_id,
                )
                self.is_ok = True

        if self.error_code:
            log.info(
                "SMS delivery error",
                to=self.to,
                error_code=self.error_code,
                error_message=self.error_message,
                appointment_id=self.appointment_id,
            )

            if self.error_code in BLOCKED_ERROR_CODES:
                self.is_blocked = True

    def __bool__(self) -> bool:
        return self.is_ok


def send_message(
    to: str,
    message: str,
    send_at: datetime.datetime | None = None,
    pod: str = stats.PodNames.TEST_POD,
    metrics_tags: Iterable[str] = (),
    notification_type: str | None = None,
    appointment_id: int | None = None,
) -> SMSDeliveryResult | None:
    """
    Send the message to the recipient

    If send_at is provided, the message will be scheduled to send at that time.
    send_at must be between 15 mins and 7 days from now.
    See https://www.twilio.com/docs/messaging/features/message-scheduling#required-parameters
    """
    if not twilio_client:
        log.info("Twilio not configured, no SMS!")
        return None
    # The isoformat() function doesn't add the Z which Twilio requires to be present
    time = send_at.strftime("%Y-%m-%dT%H:%M:%S%zZ") if send_at else None

    # only append notification type if given a populated param value
    callback_url = (
        f"{status_callback_url}?notification_type={notification_type}"
        if notification_type
        else status_callback_url
    )

    # twilio.Client.messages.create returns a MessageInstance object on success
    # it raises TwilioRestException on errors
    try:
        with ddtrace.tracer.trace("sms.send_via_twilio"):
            sms_result = twilio_client.messages.create(
                body=message,
                to=to,
                messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
                send_at=time,
                schedule_type="fixed" if send_at else None,
                status_callback=callback_url,
            )
        return SMSDeliveryResult(sms_result, appointment_id=appointment_id)
    except TwilioRestException as tre:
        log.error("Twilio REST API Error.", error=str(tre))
        stats.increment(
            "sms.twilio_api_error",
            pod_name=stats.PodNames(pod),
            tags=[*metrics_tags],
        )
        return SMSDeliveryResult(
            None,
            to=to,
            error_code=tre.code,
            error_message=tre.msg,
            appointment_id=appointment_id,
        )
    except TwilioException as te:
        log.error("SMS NOT sent due to Twilio exception", error=str(te))
        stats.increment(
            "sms.twilio_connection_error",
            pod_name=stats.PodNames(pod),
            tags=[*metrics_tags],
        )
        return SMSDeliveryResult(
            None, to=to, is_ok=False, appointment_id=appointment_id
        )


def delete_messages(
    phone_number: str,
    pod: str = stats.PodNames.TEST_POD,
    metrics_tags: Iterable[str] = (),
) -> bool:
    """
    Deletes all messages for the provided phone_number.
    Returns True if all messages are successfully deleted
    """
    if not phone_number:
        log.warn("No phone_number")
        return False
    for message in twilio_client.messages.stream(to=phone_number):
        try:
            message.delete()
        except TwilioRestException as tre:
            log.error(
                "Unable to delete message with id (%s)", message.id, error=str(tre)
            )
            stats.increment(
                "sms.twilio_delete_message_error",
                pod_name=stats.PodNames(pod),
                tags=[*metrics_tags],
            )
            return False
    return True


def cancel_message(
    sid: str, pod: str = stats.PodNames.TEST_POD, metrics_tags: Iterable[str] = ()
) -> SMSDeliveryResult:
    """
    Cancels a message scheduled in Twilio with the provided sid
    """
    try:
        message = twilio_client.messages(sid).update(status="canceled")
        return SMSDeliveryResult(message)
    except TwilioRestException as tre:
        log.error(
            f"Unable to cancel message with id {sid}",
            error=str(tre),
        )
        stats.increment(
            "sms.twilio_cancel_message_error",
            pod_name=stats.PodNames(pod),
            tags=[*metrics_tags],
        )
        return SMSDeliveryResult(None, is_ok=False)
