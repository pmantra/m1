from traceback import format_exc

from flask import request

from common.services.api import UnauthenticatedResource
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.billing.errors import BillingServicePGMessageProcessingError
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class BillPaymentGatewayEventConsumptionResource(UnauthenticatedResource):
    @staticmethod
    def post():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        See api/direct_payment/openapi.yaml: paths./api/v1/direct_payment/billing/ingest_payment_gateway_event
        Modelled so callers can fire and forget.
        :return: Payload received", 202
        :rtype: tuple(str, int)
        """
        try:
            log.info("Received payment gateway payload.")
            billing_service = BillingService(
                session=db.session,
                payment_gateway_base_url=INTERNAL_TRUST_PAYMENT_GATEWAY_URL,
            )
            log.info("Created billing service object.")
            payload = request.json if request.is_json else None
            log.info("Processing payment gateway payload.")
            billing_service.process_payment_gateway_event_message(payload)
            log.info("Processed payment gateway payload.")
        except BillingServicePGMessageProcessingError as known_ex:
            log.error(
                "Failed to process payment gateway payload",
                reason=known_ex.message,
                ex_msg=format_exc(),
            )
        except Exception as ex:
            log.error(
                "Unexpectedly failed to process payment gateway payload",
                reason=str(ex),
                ex_msg=format_exc(),
            )
        return "Payload received", 202
