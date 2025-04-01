import datetime
import os

from flask import request
from flask_restful import abort
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.payments import Invoice
from common import stats
from common.services.api import UnauthenticatedResource
from common.services.stripe import read_webhook_event
from emails import transfer_complete
from models.profiles import PractitionerProfile
from storage.connection import db
from tasks.queues import job
from utils import braze_events
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)

STRIPE_SIGNATURE_SECRET_KEY = "STRIPE_SIGNATURE_SECRET_KEY"


class StripeWebHooksResource(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # we want stripe to either get a 200 or a non-2xx - they won't
        # acknowledge anything else https://stripe.com/docs/webhooks
        raw_data = request.get_data()
        if not raw_data:
            log.info("No data for webhook!")
            # this is an exception to the 2xx and 5xx rule :)
            abort(400)

        header_signature = request.headers.get("STRIPE_SIGNATURE")
        signature_secret = os.getenv(STRIPE_SIGNATURE_SECRET_KEY)
        if signature_secret and not header_signature:
            log.info("Signature is needed.")
            abort(400)

        event = read_webhook_event(
            request.get_json(), raw_data, header_signature, signature_secret  # type: ignore[arg-type] # Argument 2 to "read_webhook_event" has incompatible type "bytes"; expected "str"
        )
        if not event:
            abort(400)

        if event.type not in ["payout.paid", "payout.failed"]:  # type: ignore[union-attr] # Item "None" of "Optional[StripeObject]" has no attribute "type"
            return "", 200

        if not event.livemode:  # type: ignore[union-attr] # Item "None" of "Optional[StripeObject]" has no attribute "livemode"
            # test webhooks can be ignored!
            log.debug("Ignoring webhook, not in livemode", data=raw_data)
            return "", 200

        if not event.account:  # type: ignore[union-attr] # Item "None" of "Optional[StripeObject]" has no attribute "account"
            log.info(
                "No connect account for payout hook.",
                event_id=event.id,  # type: ignore[union-attr] # Item "None" of "Optional[StripeObject]" has no attribute "id"
                request=event.request,  # type: ignore[union-attr] # Item "None" of "Optional[StripeObject]" has no attribute "request"
            )

            stats.increment(
                metric_name="payments.resources.stripe_webhook.payout",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:no_connect_account"],
            )

            return "", 200

        service_ns_tag = "provider_payments"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        confirm_payout.delay(event, service_ns=service_ns_tag, team_ns=team_ns_tag)

        log.debug("Processed webhook")
        return "", 200

    @staticmethod
    def get_invoices_for_amount(invoices, amount):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Returns all the invoices if the total value matches the total amount or
        find a single invoice which matches the amount coming from stripe.
        """
        total_amount = sum(invoice.value for invoice in invoices) * 100
        if total_amount != amount:
            invoices = [
                invoice for invoice in invoices if invoice.value * 100 == amount
            ]
            if len(invoices) > 1:
                return invoices[:1]

        return invoices


@job(traced_parameters=("event",))
def confirm_payout(event):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        profile = (
            db.session.query(PractitionerProfile)
            .filter(PractitionerProfile.stripe_account_id == event.account)
            .one()
        )
    except NoResultFound:
        log.info("No PractitionerProfile for webhook", event_data=event)
        stats.increment(
            metric_name="payments.resources.stripe_webhook.payout",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=["error:true", "error_cause:no_practitioner"],
        )
        return "", 200

    invoices = (
        db.session.query(Invoice)
        .filter(
            Invoice.recipient_id == profile.stripe_account_id,
            Invoice.completed_at.is_(None),
            Invoice.started_at.isnot(None),
            Invoice.failed_at.is_(None),
            Invoice.transfer_id.isnot(None),
            Invoice.started_at.between(
                (datetime.datetime.utcnow() - datetime.timedelta(days=14)),
                datetime.datetime.utcnow(),
            ),
        )
        .all()
    )

    if not invoices:
        log.info("No invoices for webhook", event_data=event)
        stats.increment(
            metric_name="payments.resources.stripe_webhook.payout",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=["error:true", "error_cause:no_invoices"],
        )
        return "", 200

    if len(invoices) > 1:
        invoices = StripeWebHooksResource.get_invoices_for_amount(
            invoices, event.data.object.amount
        )
        if not invoices:
            log.info("No invoices match the amount for webhook", event_data=event)
            stats.increment(
                metric_name="payments.resources.stripe_webhook.payout",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:no_invoices_match_amount"],
            )
            return "", 200

    if event.type == "payout.failed":
        for invoice in invoices:
            invoice.confirm_payout_failure()
        db.session.commit()
        stats.increment(
            metric_name="payments.resources.stripe_webhook.payout.failed",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=["error:false"],
        )
    elif event.type == "payout.paid":
        entries = []
        amount = 0
        for invoice in invoices:
            invoice = invoice.confirm_payout_success()
            entries.extend(invoice.entries)
            amount += invoice.value
        transfer_complete(invoices=invoices, amount=amount, entries=entries)
        # send the practitioner an email to let them know they have $$
        braze_events.practitioner_invoice_payment(
            practitioner=profile.user,
            amount=amount,
            payment_date=invoices[0].completed_at,
        )
        db.session.commit()
        stats.increment(
            metric_name="payments.resources.stripe_webhook.payout.paid",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=["error:false"],
        )
