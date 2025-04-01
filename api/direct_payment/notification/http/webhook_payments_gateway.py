from traceback import format_exc

from flask import request

from common.services.api import UnauthenticatedResource
from direct_payment.notification.errors import PaymentGatewayMessageProcessingError
from direct_payment.notification.lib.payment_gateway_handler import (
    process_payment_gateway_message,
)
from utils.log import logger

log = logger(__name__)


class NotificationServicePaymentGatewayEventConsumptionResource(
    UnauthenticatedResource
):
    @staticmethod
    def post():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        payload = ""
        try:
            payload = request.json if request.is_json else None
            res = process_payment_gateway_message(payload)  # type: ignore[arg-type] # Argument 1 to "process_payment_gateway_message" has incompatible type "str"; expected "Dict[Any, Any]"
            if res:
                return "Payload received and queued for processing.", 202
            else:
                return "Payload rejected/unsupported.", 202

        except PaymentGatewayMessageProcessingError as known_ex:
            log.error(
                "Failed to process payment gateway payload",
                reason=known_ex.message,
                payload=payload,
            )
            return "Failed to process payment gateway payload.", 400
        except Exception:
            log.error(
                "Unexpectedly failed to process payment gateway payload.",
                reason=format_exc(),
                payload=request.data,
            )
            return "Unexpectedly failed to process payment gateway payload", 500
