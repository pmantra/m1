import hashlib
from datetime import date, datetime
from typing import List, Optional, Tuple

from dateutil.relativedelta import relativedelta
from redset.locks import LockTimeout
from sqlalchemy import extract
from sqlalchemy.orm import joinedload

from appointments.models.payments import FeeAccountingEntry, Invoice
from authn.models.user import User
from common import stats
from common.services.stripe import StripeReimbursementHandler
from messaging.models.messaging import Channel, ChannelUsers, Message
from models.profiles import PractitionerProfile
from payments.models.constants import PROVIDER_PAYMENTS_EMAIL
from storage.connection import db
from tasks.queues import job, retryable_job
from utils.cache import RedisLock
from utils.log import logger
from utils.mail import send_message
from utils.payments import add_fees_to_invoices
from utils.reporting import failed_invoices_csv, invoices_csv
from utils.slack_v2 import notify_provider_ops_alerts_channel
from wallet.models.constants import ReimbursementRequestState
from wallet.models.reimbursement import ReimbursementRequest

log = logger(__name__)


def create_hash_from_fees(valid_fees: List[FeeAccountingEntry]) -> str:
    text = "".join(f"{fee.practitioner_id}:{fee.amount}" for fee in valid_fees)
    fee_hash = hashlib.sha1(text.encode()).hexdigest()
    return fee_hash


def get_fees(months_ago: int = 1) -> Tuple[List[FeeAccountingEntry], str]:
    now = datetime.utcnow()
    one_month_ago = date(now.year, now.month, 1) - relativedelta(months=months_ago)
    fees = (
        db.session.query(FeeAccountingEntry)
        .filter(
            extract("year_month", FeeAccountingEntry.created_at)
            == extract("year_month", one_month_ago)  # type: ignore[arg-type] # Argument 2 to "Extract" has incompatible type "date"; expected "ClauseElement"
        )
        .options(
            joinedload(FeeAccountingEntry.message)
            .joinedload(Message.channel)
            .joinedload(Channel.participants)
            .joinedload(ChannelUsers.user)
            .options(
                joinedload(User.practitioner_profile).joinedload(
                    PractitionerProfile.verticals
                ),
                joinedload(User.member_profile),
            ),
            joinedload(FeeAccountingEntry.appointment),
        )
        .order_by(FeeAccountingEntry.id)
        .all()
    )
    fee_hash = create_hash_from_fees(fees)
    log.info(
        "Found fees from previous month",
        count=len(fees),
        month=one_month_ago,
        fee_hash=fee_hash,
    )
    return fees, fee_hash


def create_fee_invoices(
    valid_fees: List[FeeAccountingEntry],
    to_email: Optional[str] = PROVIDER_PAYMENTS_EMAIL,
    fee_hash: str = None,  # type: ignore[assignment] # Incompatible default for argument "fee_hash" (default has type "None", argument has type "str")
) -> Tuple[List[Invoice], str]:
    if not fee_hash:
        fee_hash = create_hash_from_fees(valid_fees)
    invoices = add_fees_to_invoices(valid_fees, skip_malpractice_only=True)
    log.info("Created invoices", count=len(invoices))
    invoices_csv_text = "".join(invoices_csv(invoices))
    email_text = (
        "Found {} valid fees. Enter this code on the payment tools page to "
        "start transfers on these invoices: {}".format(len(valid_fees), fee_hash)
    )

    if to_email:
        now = datetime.utcnow()
        send_message(
            to_email=to_email,
            subject=f"Fee cleanup {now.strftime('%Y-%m-%d')}",
            text=email_text,
            csv_attachments=[("invoices.csv", invoices_csv_text)],
            internal_alert=True,
            production_only=True,
        )

    return invoices, fee_hash


@job
def generate_invoices_from_fees(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    months_ago: int = 1,
    to_email: Optional[str] = PROVIDER_PAYMENTS_EMAIL,
):
    """
    This command is safe to re-run.
    It is idempotent. It sends an email to accounting.
    They receive a hash of the fee data and re-enter that hash in admin before we process payments.
    """
    notify_provider_ops_alerts_channel(
        notification_title="Generate Invoices From Fees Process Started",
        notification_body=f"months_ago: {months_ago}, to_email: {to_email}",
        production_only=True,
    )
    log.info(
        "Generate Invoices From Fees Process Started",
        months_ago=months_ago,
        to_email=to_email,
    )
    valid_fees, fee_hash = get_fees(months_ago=months_ago)
    invoices, _ = create_fee_invoices(valid_fees, to_email=to_email, fee_hash=fee_hash)
    send_message(
        to_email=PROVIDER_PAYMENTS_EMAIL,
        subject="Generate Invoices From Fees Process Complete",
        text=f"Invoice count: {len(invoices)}",
        internal_alert=True,
        production_only=True,
    )
    log.info(
        "Generate Invoices From Fees Process Complete",
        invoice_count=len(invoices),
        fee_count=len(valid_fees),
    )
    return invoices, fee_hash


def process_invoices_from_fees(valid_fee_ids: List[int], expected_fee_hash: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    This job process fee data, actually moving the money. It is not idempotent.
    It should be triggered from admin  after the email of invoice data from the get_fees() job is verified.
    """
    log.info("Invoice Transfers - Process invoices from clean fees")
    valid_fees = FeeAccountingEntry.query.filter(
        FeeAccountingEntry.id.in_(valid_fee_ids)
    ).all()
    invoices, fee_hash = create_fee_invoices(
        valid_fees, to_email=PROVIDER_PAYMENTS_EMAIL
    )
    if expected_fee_hash != fee_hash:
        send_message(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Fee Payments Have Encountered An Unexpected Error",
            text=f"Expected Fee Hash: {expected_fee_hash}, Generated Fee Hash: {fee_hash}",
            internal_alert=True,
            production_only=True,
        )
        return

    start_invoices.delay(
        team_ns="payments_platform",
        job_timeout=30 * 60,
        invoice_ids=[i.id for i in invoices],
    )


@job
def check_invoices(to_email=PROVIDER_PAYMENTS_EMAIL):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    now = datetime.utcnow()
    start_at = date(now.year, now.month, 1) - relativedelta(months=3)
    invoices = db.session.query(Invoice).filter(Invoice.created_at >= start_at).all()
    unpaid = []
    for invoice in invoices:
        if invoice.entries and (not invoice.transfer_id or not invoice.started_at):
            unpaid.append(invoice)
    if unpaid:
        send_message(
            to_email=to_email,
            subject=f"{len(unpaid)} Invoices not paid!",
            text=f"Invoice ids: {[i.id for i in unpaid]}",
            csv_attachments=[("invoices.csv", "".join(invoices_csv(unpaid)))],
            internal_alert=True,
            production_only=True,
        )


STATS_PREFIX = "api.tasks.payments"


@job
def check_failed_payments(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    to_email=PROVIDER_PAYMENTS_EMAIL,
):
    failed_invoices = (
        db.session.query(Invoice)
        .filter(
            Invoice.started_at.isnot(None),
            Invoice.completed_at.is_(None),
            Invoice.created_at >= datetime.utcnow() - relativedelta(months=3),
        )
        .all()
    )
    if not failed_invoices:
        log.info("No failed payments! :D")
        return
    send_message(
        to_email=to_email,
        subject="Practitioner Payments - Payments initiated but failing",
        text="See attachment for details. Bank account status is as defined "
        "here: https://stripe.com/docs/api#customer_bank_account_object-status",
        csv_attachments=[
            ("failed_invoices.csv", "".join(failed_invoices_csv(failed_invoices)))
        ],
        internal_alert=True,
        production_only=True,
    )

    stats.increment(
        metric_name=f"{STATS_PREFIX}.failed",
        pod_name=stats.PodNames.PAYMENTS_POD,
        metric_value=len(failed_invoices),
        tags=["error:true", "status:payments_initiated_but_failing"],
    )


@job(traced_parameters=("invoice_ids",))
def start_invoices(invoice_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(
        "Invoice Transfers - Starting transfers for invoice ids",
        invoice_ids=invoice_ids,
    )
    invoices = db.session.query(Invoice).filter(Invoice.id.in_(invoice_ids))
    transfer_errors = {}
    try:
        with RedisLock("invoice_transfers_in_progress", expires=180):
            for invoice in invoices:
                try:
                    invoice.start_transfer()
                    db.session.add(invoice)
                    db.session.commit()
                except Exception as e:
                    transfer_errors[invoice.id] = str(e)
            if len(transfer_errors) > 0:
                log.warning(
                    "Error transferring invoices.",
                    transfer_errors=str(transfer_errors),
                )
                raise Exception

    except LockTimeout:
        send_message(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Could not start invoice transfers",
            text="Other invoice transfers already in progress, wait a bit and "
            "try again.",
            internal_alert=True,
            production_only=True,
        )

        stats.increment(
            metric_name=f"{STATS_PREFIX}.failed",
            pod_name=stats.PodNames.PAYMENTS_POD,
            metric_value=len(invoices),
            tags=["error:true", "status:other_invoice_transfers_in_progress"],
        )
    except Exception:
        log.exception("Error starting invoice transfers")
        send_message(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Could not start invoice transfers",
            text=f"Error starting invoice transfers. Errors per invoice id: {transfer_errors}",
            internal_alert=True,
            production_only=True,
        )

        stats.increment(
            metric_name=f"{STATS_PREFIX}.failed",
            pod_name=stats.PodNames.PAYMENTS_POD,
            metric_value=len(transfer_errors),
            tags=["error:true", "status:could_not_start_invoice"],
        )
    else:
        send_message(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Successfully started invoice transfers",
            text=f"Successfully started invoice transfers for these invoice ids: {invoice_ids}",
            internal_alert=True,
            production_only=True,
        )


@retryable_job
def process_stripe_reimbursement_status(event):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Queue to handle event data from the stripe reimbursements webhook while returning quick responses to Stripe."""
    if not event.type == "payout.paid" and not event.type == "payout.failed":
        log.info(
            "The reimbursements webhook does not process this event type.",
            stripe_event=event,
        )
    else:
        stripe_event_data = event.data.object
        if not (
            stripe_event_data.metadata
            and StripeReimbursementHandler.PAYOUT_METADATA_ID_FIELD
            in stripe_event_data.metadata
        ):
            log.exception(
                "A stripe reimbursement without reimbursement request id metadata cannot be tracked.",
                stripe_reimbursement_id=stripe_event_data.id,
            )
            send_message(
                to_email=PROVIDER_PAYMENTS_EMAIL,
                subject="Reimbursement missing expected metadata",
                text=f"This stripe transfer is not associated with a reimbursement request: {stripe_event_data.id}.",
                internal_alert=True,
                production_only=True,
            )
            return
        else:
            request = ReimbursementRequest.query.get(
                stripe_event_data.metadata[
                    StripeReimbursementHandler.PAYOUT_METADATA_ID_FIELD
                ]
            )
            if not request:
                log.exception(
                    "No Reimbursement found for stripe payout request metadata.",
                    stripe_reimbursement_id=stripe_event_data.id,
                )
                send_message(
                    to_email=PROVIDER_PAYMENTS_EMAIL,
                    subject="Stripe Payout missing connected Reimbursement Request",
                    text=f"This stripe transfer is not associated with a reimbursement request: {stripe_event_data.id}.",
                    internal_alert=True,
                    production_only=True,
                )
                return
            if event.type == "payout.failed":
                log.exception(
                    "Stripe payout event failed.",
                    reimbursement_request=request,
                    stripe_reimbursement_id=stripe_event_data.id,
                )
                send_message(
                    to_email=PROVIDER_PAYMENTS_EMAIL,
                    subject="Stripe Payout failed in Stripe",
                    text=f"The Stripe payout attempt failed with id: {stripe_event_data.id}.",
                    internal_alert=True,
                    production_only=True,
                )
                request.state = ReimbursementRequestState.FAILED
                db.session.add(request)
                db.session.commit()
                return
            if (
                not request.reimbursement_payout_date
                or stripe_event_data.amount != request.amount
            ):
                log.exception(
                    "Stripe payout event does not match the Reimbursement Request from the relevant metadata.",
                    reimbursement_request=request,
                    stripe_reimbursement_id=stripe_event_data.id,
                )
                send_message(
                    to_email=PROVIDER_PAYMENTS_EMAIL,
                    subject="Stripe Reimbursement does not match the Reimbursement Request",
                    text=f"This stripe payout: {stripe_event_data.id} is inconsistent with this reimbursement request: "
                    f"{request.id}. The request may be lacking a payout date or the stripe payout may be for "
                    "the wrong amount of reimbursement funds.",
                    internal_alert=True,
                    production_only=True,
                )
                return
            request.state = ReimbursementRequestState.REIMBURSED
            db.session.add(request)
            db.session.commit()
    return


@job
def start_invoice_transfers_job(provided_fee_hash: str, override_hash: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    This job process fee data, actually moving the money. It is not idempotent.
    Run as a delay job, otherwise it will likely timeout.
    Override provided for when a payments engineer needs to run manually in a prod shell.
    """
    log.info("Invoice Transfers - Started")

    fees, fee_hash = get_fees()
    log.info("Invoice Transfers - Fees gathered")

    # Verify the hash unless overridden
    if override_hash:
        log.info("Invoice Transfers - Fee hash override")
    elif fee_hash != provided_fee_hash:
        log.error(
            "Invoice Transfers - Invalid fee hash provided",
            provided_fee_hash=provided_fee_hash,
            fee_hash=fee_hash,
        )
        send_message(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job failed before starting - invalid fee hash",
            text=f"Provided Fee Hash: {provided_fee_hash}, Generated Fee Hash: {fee_hash}",
            internal_alert=True,
            production_only=True,
        )
        return False

    if not fees:
        log.error(
            "Invoice Transfers - No fees found",
        )
        send_message(
            to_email=PROVIDER_PAYMENTS_EMAIL,
            subject="Invoice Transfer job failed before starting - no fees found",
            text="No fees found for the Invoice Transfer job to process.",
            internal_alert=True,
            production_only=True,
        )
        return False

    send_message(
        to_email=PROVIDER_PAYMENTS_EMAIL,
        subject="Invoice Transfer job started",
        text="The Invoice Transfer job has started, you will be notified upon completion.",
        internal_alert=True,
        production_only=True,
    )

    process_invoices_from_fees(
        valid_fee_ids=[fee.id for fee in fees], expected_fee_hash=fee_hash
    )

    log.info("Invoice Transfers - Completed")
    send_message(
        to_email=PROVIDER_PAYMENTS_EMAIL,
        subject="Invoice Transfer job completed",
        text="The Invoice Transfer job has been completed.",
        internal_alert=True,
        production_only=True,
    )
    return True
