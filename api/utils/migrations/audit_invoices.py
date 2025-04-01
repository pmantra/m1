import datetime
from decimal import Decimal

from appointments.models.payments import (  # type: ignore[attr-defined] # Module "appointments.models.payments" has no attribute "stripe"
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    Invoice,
    stripe,
)
from storage.connection import db


def audit_invoices():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    invoices = (
        db.session.query(Invoice)
        .filter(Invoice.created_at >= datetime.date(2018, 4, 1))
        .all()
    )
    fee_ids = []
    for invoice in invoices:
        fee = _check_invoice(invoice)
        if fee is not None:
            fee_ids.append(fee.id)
    print("Done! Created fees: {}".format(fee_ids))


def _check_invoice(invoice):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    print("Checking invoice: {}".format(invoice.id))
    try:
        transfer = stripe.Transfer.retrieve(invoice.transfer_id)
    except stripe.InvalidRequestError:
        print("Could not retrieve transfer, skipping...")
        return

    practitioner = invoice.practitioner
    if practitioner is None:
        print("Could not determine practitioner for invoice, skipping...")
        return

    transfer_amount = Decimal(transfer.amount) / Decimal(100)
    if transfer_amount != invoice.value:
        print("Invoice value != transfer value")
        print("{} != {}".format(invoice.value, transfer_amount))
        correction_amount = invoice.value - transfer_amount
        if correction_amount > 0:
            print("Creating fee...")
            fee = FeeAccountingEntry(
                amount=correction_amount,
                practitioner=practitioner,
                type=FeeAccountingEntryTypes.APPOINTMENT,
            )
            db.session.add(fee)
            db.session.commit()
            return fee
        else:
            print("Practitioner was overpaid, skipping fee.")
