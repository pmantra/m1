from flask import Response, request
from twilio.twiml.messaging_response import MessagingResponse

from appointments.services.acknowledgement import (
    acknowledge_appointment_by_phone_number,
)
from common.services.api import UnauthenticatedResource
from utils.data import normalize_phone_number
from utils.log import logger

log = logger(__name__)


class BookingsReplyResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = request.form

        log.debug(f"INCOMING ACK for message ({data['MessageSid']})")
        log.debug("MessageSid: %s", data["MessageSid"])
        log.debug("Body: %s", data["Body"])

        incoming_phone_number, _ = normalize_phone_number(data["From"], None)

        reply = acknowledge_appointment_by_phone_number(
            incoming_phone_number, data["MessageSid"], body=data["Body"]
        )

        resp = MessagingResponse()
        # If there are no acks and someone sends an sms to us, do not reply with a message
        if reply:
            resp.message(reply)
        res = Response(str(resp))
        res.headers["Content-Type"] = "application/xml"
        return res
