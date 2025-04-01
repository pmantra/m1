from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from common import stats
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class FeeRecipientException(Exception):
    pass


def add_fees_to_invoices(fees: list, skip_malpractice_only: bool = False) -> list:
    """
    Add all the given fees to the relevant practitioner invoices.

    :param fees: List of FeeAccountingEntries to add to invoices
    :param skip_malpractice_only: If all the given fees for a practitioner are
        malpractice fees, skip creating the invoice.
    :return:
    """
    from appointments.models.payments import Invoice

    log.info("Adding fees to invoices", count=len(fees))

    by_practitioner = defaultdict(list)

    stripe_recipient_ids = set()
    for fee in fees:
        prac_id = None
        if fee.appointment:
            prac_id = fee.appointment.practitioner.id
        elif fee.message and fee.message.channel and fee.message.channel.practitioner:
            prac_id = fee.message.channel.practitioner.id
        elif fee.practitioner:
            prac_id = fee.practitioner.id
        if prac_id:
            by_practitioner[prac_id].append(fee)

        stripe_recipient_ids.add(fee.stripe_recipient_id)

    log.debug(
        "Checking fees for practitioners", practitioner_count=len(by_practitioner)
    )

    # Optimization: load all active invoices by stripe_recipient_id first
    # Only look at invoices created after the begining of last month
    now = datetime.utcnow()
    last_month_start = datetime(now.year, now.month, 1) - relativedelta(months=1)
    active_invoices = (
        db.session.query(Invoice)
        .filter(
            Invoice.recipient_id.in_(stripe_recipient_ids),
            Invoice.started_at == None,
            Invoice.created_at >= last_month_start,
        )
        # Sort by created_at DESC so that when we take the last one, we're taking the oldest
        .order_by(Invoice.created_at.desc())
        .all()
    )
    log.info("Found active_invoices", n_active_invoices=len(active_invoices))
    active_invoices_by_recipient_id = {}
    for invoice in active_invoices:
        if invoice.recipient_id in active_invoices_by_recipient_id:
            log.warning(
                "There should only be one invoice per recipient_id. We are seeing more than one",
                recipient_id=invoice.recipient_id,
                existing_invoice_id=active_invoices_by_recipient_id[
                    invoice.recipient_id
                ].id,
                replacing_invoice_id=invoice.id,
            )
        active_invoices_by_recipient_id[invoice.recipient_id] = invoice

    invoices = []
    i = 0
    for prac_id, p_fees in by_practitioner.items():
        if skip_malpractice_only and not [f for f in p_fees if f.amount > 0]:
            log.info(
                "All fees for practitioner are for malpractice, skipping invoice.",
                practitioner_id=prac_id,
            )
            continue
        recipient_id = p_fees[0].stripe_recipient_id
        if not recipient_id:
            log.info(
                "Cannot add fee without a recipient for practitioner!",
                practitioner_id=prac_id,
            )
            continue

        active_invoice = active_invoices_by_recipient_id.get(recipient_id)
        if (
            active_invoice
            and active_invoice.value > 0
            and [
                fee
                for fee in active_invoice.entries
                if fee.created_at < last_month_start
            ]
        ):
            log.info(
                "Practitioner already had invoice with entries",
                invoice_id=active_invoice.id,
                prac_id=active_invoice.recipient_id,
                fee_ids=[fee.id for fee in active_invoice.entries],
            )
            stats.increment(
                metric_name="api.utils.payments.add_fees_to_invoices.prac_fee_older_than_one_month",
                pod_name=stats.PodNames.PAYMENTS_POD,
            )
        if not active_invoice:
            log.info("Creating new invoice for recipient_id", recipient_id=recipient_id)
            active_invoice = Invoice()
            # TODO: add audit log create once generate_invoices_from_fees cron is updated to take a user param
            active_invoice.recipient_id = recipient_id

        for fee in p_fees:
            log.info(
                "Will try to add fee to invoice",
                fee_id=fee.id,
                invoice_id=active_invoice.id,
            )
            if fee.stripe_recipient_id == recipient_id:
                log.info(
                    "Adding fee to invoice", fee_id=fee.id, invoice_id=active_invoice.id
                )
                active_invoice.add_entry(fee)
                # TODO: add audit log update once generate_invoices_from_fees cron is updated to take a user param
            else:
                log.warning(
                    "Fee stripe_recipient_id does not match expected recipient_id",
                    fee_stripe_recipient_id=fee.stripe_recipient_id,
                    recipient_id=recipient_id,
                    fee_id=fee.id,
                    invoice_id=active_invoice.id,
                )
                raise FeeRecipientException(
                    f"{fee} does not match recipient: {recipient_id}"
                )

        invoices.append(active_invoice)
        db.session.add(active_invoice)
        # TODO: add audit log update once generate_invoices_from_fees cron is updated to take a user param

        # Save once every 50 practitioners
        if i % 50 == 0:
            db.session.commit()
        i += 1

    db.session.commit()

    return invoices


def convert_dollars_to_cents(amount):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not isinstance(amount, Decimal):
        amount = Decimal(f"{amount}")
        log.warn(
            "The amount to be converted to cents is not Decimal. "
            "Converting amount to decimal for precision arithmetic"
        )
    log.debug("Converting amount into cents: %s", amount)
    amount = int(amount * 100)
    log.debug("Got %s cents", amount)
    return amount


def convert_cents_to_dollars(amount: int) -> float:
    return amount / 100
