from __future__ import annotations

import os

import ddtrace.ext
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from utils.log import logger

log = logger(__name__)

TWILIO_VERIFY_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
    client = None
else:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

DEFAULT_COUNTRY_CODE = 1  # US


class TwilioApiException(Exception):
    """Generic error from the Twilio API. Check below for more specific exceptions."""

    pass


class TwilioRateLimitException(TwilioApiException):
    pass


def _check_rate_limit(err: TwilioRestException):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if err.status == 429:
        log.debug("Rate limited by Twilio", body=err.msg)
        raise TwilioRateLimitException(err)


def _log_twilio_error(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    description: str, err: TwilioRestException, sms_phone_number: str
):
    # only log last 4 digits of the phone number
    if not err:
        log.error("error sent from the Twilio is None")
        return
    if not sms_phone_number:
        log.error("No sms phone number is None")
        return
    log.error(
        err.msg,
        status_code=err.status,
        errors=err.msg,
        sms_phone_number=sms_phone_number[-4:],
    )


@ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.WEB)
def request_otp_via_sms(sms_phone_number: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if client is None:
        log.warning("No Twilio client initialized. Not sending SMS verification code.")
        return False

    try:
        client.verify.v2.services(TWILIO_VERIFY_SID).verifications.create(
            to=sms_phone_number, channel="sms"
        )
    except TwilioRestException as err:
        _log_twilio_error("Error sending SMS token to user", err, sms_phone_number)
        _check_rate_limit(err)

        raise TwilioApiException("Error sending SMS token to user")

    return True


@ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.WEB)
def verify_otp(sms_phone_number: str, token: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if client is None:
        log.warning("No Twilio client initialized. Not verifying code.")
        return False

    try:
        verification_check = client.verify.v2.services(
            TWILIO_VERIFY_SID
        ).verification_checks.create(to=sms_phone_number, code=token)
    except TwilioRestException as err:
        # This could be due to the token expiring, which occurs after 10 minutes
        _log_twilio_error("Error verifying MFA code", err, sms_phone_number)
        return False

    return verification_check.status == "approved"
