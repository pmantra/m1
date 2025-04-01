from flask import request
from flask_restful import abort

from common.services.api import UnauthenticatedResource
from common.services.stripe import StripeReimbursementHandler
from tasks.payments import process_stripe_reimbursement_status
from utils.log import logger

log = logger(__name__)


class StripeReimbursementWebHookResource(UnauthenticatedResource):
    """Webhook that receives events from the reimbursement stripe account only."""

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        data = request.get_json()
        header_signature = request.headers["STRIPE_SIGNATURE"]
        if not data or not header_signature:
            log.info("No data for reimbursements webhook.")
            abort(400)

        event = StripeReimbursementHandler.read_webhook_event(data, header_signature)
        if not event:
            abort(400)

        # handle data with a queue to notify stripe of immediate receipt of data
        process_stripe_reimbursement_status.delay(event)
        return "", 200
