import dateparser

from appointments.models.payments import (
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    Invoice,
)
from authn.models.user import User
from data_admin.maker_base import _MakerBase
from data_admin.makers.appointments import AppointmentMaker
from data_admin.makers.messaging import MessageMaker
from storage.connection import db


class InvoiceMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        recipient = User.query.filter_by(email=spec.get("recipient")).one()
        invoice = Invoice(recipient_id=recipient.id)
        for attr in ["created_at", "started_at", "completed_at"]:
            if spec.get(attr):
                setattr(invoice, attr, dateparser.parse(spec.get(attr)))
        db.session.add(invoice)
        db.session.flush()
        if "fees" in spec and isinstance(spec["fees"], list):
            for fee_spec in spec["fees"]:
                FeeAccountingEntryMaker().create_object_and_flush(
                    fee_spec, invoice=invoice
                )
        return invoice


class FeeAccountingEntryMaker(_MakerBase):
    def create_object(self, spec, invoice=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        fee = FeeAccountingEntry(
            amount=spec.get("amount"), type=FeeAccountingEntryTypes.UNKNOWN
        )

        if invoice is not None:
            fee.invoice = invoice
        if spec.get("practitioner"):
            practitioner = User.query.filter_by(email=spec.get("practitioner")).one()
            fee.practitioner = practitioner
            fee.type = FeeAccountingEntryTypes.ONE_OFF
        if spec.get("appointment"):
            appointment = AppointmentMaker().create_object_and_flush(
                spec.get("appointment")
            )
            fee.appointment = appointment
            fee.type = FeeAccountingEntryTypes.APPOINTMENT
        if spec.get("message"):
            message = MessageMaker().create_object_and_flush(spec.get("message"))
            fee.message = message
            fee.type = FeeAccountingEntryTypes.MESSAGE
        db.session.add(fee)
        return fee
