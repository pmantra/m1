import os
from traceback import format_exc

from flask import request

from appointments.services.acknowledgement import update_member_appointment_ack_sent
from common import stats
from common.services.api import UnauthenticatedResource
from messaging.schemas.twilio import TwilioMessageStatusEnum, TwilioStatusWebhook
from utils.constants import TWILIO_SMS_DELIVERY_ERROR
from utils.log import logger

log = logger(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "twilio_account_sid")


class TwilioStatusWebhookResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        This endpoint receives status updates from Twilio about messages that have been
        sent using Twilio's Messaging service. For additional information on how Twilio
        uses this endpoint see https://www.twilio.com/docs/sms/tutorials/how-to-confirm-delivery-python
        """
        data = request.form
        notification_type = request.args.get("notification_type")
        log.debug("Processing Twilio webhook with keys: %s.", ", ".join(data.keys()))

        try:
            webhook_request = TwilioStatusWebhook.from_request(request.form)
        except Exception as e:
            log.error(
                "Could not load Twilio webhook payload: %s.", e, traces=format_exc()
            )
            return ("", 202)

        if not self.account_sid_valid(webhook_request.AccountSid):
            return ("", 202)

        if webhook_request.has_error_message_status():
            # See https://www.twilio.com/docs/api/errors/twilio-error-codes.json for SMS delivery error codes
            log.error(
                "Message was not delivered",
                message_sid=webhook_request.MessageSid,
                message_status=webhook_request.MessageStatus,
                error_code=webhook_request.ErrorCode,
                start_of_phone_number=webhook_request.To[:4],
                notification_type=notification_type,
            )

            stats.increment(
                metric_name=TWILIO_SMS_DELIVERY_ERROR,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    f"reason:{webhook_request.ErrorCode}",
                    f"notification_type:{notification_type}",
                ],
            )

        elif webhook_request.MessageStatus == TwilioMessageStatusEnum.SENT.value:
            update_member_appointment_ack_sent(webhook_request.MessageSid)

        return ("", 204)

    @classmethod
    def account_sid_valid(cls, account_sid):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if TWILIO_ACCOUNT_SID == account_sid:
            return True
        log.warn(
            "Twilio webhook failed verification with account_sid: (%s)", account_sid
        )
        return False
