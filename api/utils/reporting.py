import csv
import io
import json
from collections import OrderedDict

from sqlalchemy import or_
from sqlalchemy.orm import aliased

from appointments.models.appointment import Appointment
from appointments.models.payments import FeeAccountingEntry, Invoice
from common.services.stripe import StripeConnectClient
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from messaging.models.messaging import Channel, ChannelUsers, Message
from models.products import Product
from models.profiles import PractitionerProfile
from models.verticals_and_specialties import Vertical, is_cx_vertical_name
from payments.models.practitioner_contract import PractitionerContract
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class GeneratorIO(io.StringIO):
    def read_and_flush(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Write the value by returning it, instead of storing in a buffer."""
        self.seek(0)
        data = self.read()
        self.seek(0)
        self.truncate()
        return data


def appointments_csv(start_at, end_at):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    report = GeneratorIO()
    fieldnames = [
        "id",
        "member",
        "member_id",
        "practitioner",
        "code",
        "practitioner_id",
        "vertical_display_names",
        "created_at",
        "state",
        "scheduled_start",
        "scheduled_end",
        "member_started_at",
        "member_ended_at",
        "practitioner_started_at",
        "practitioner_ended_at",
        "cancelled_at",
        "cancelled_by_user_id",
        "anonymous",
        "credit_spent",
        "dollar_spent",
        "fee_paid",
        "fee_paid_at",
        "ratings",
        "comments",
        "credit_used_ids",
        "codes_for_credits",
        "booked_platform",
        "member_started_platform",
    ]
    writer = csv.DictWriter(report, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    appointments = Appointment.query.filter(
        Appointment.scheduled_start >= start_at, Appointment.scheduled_end <= end_at
    ).all()

    for appointment in appointments:
        profile = appointment.practitioner.practitioner_profile
        display_names = ",".join(v.marketing_name for v in profile.verticals)

        ratings = appointment.json.get("ratings", {})
        ratings = OrderedDict(sorted(ratings.items(), key=lambda t: t[0]))

        codes_used = []
        for c in appointment.credits:
            codes_used.append(
                c.referral_code_use.code.code if c.referral_code_use else None
            )
        platforms = appointment.json.get("platforms", {})

        writer.writerow(
            {
                "id": appointment.id,
                "member": appointment.member.email,
                "practitioner": appointment.practitioner.email,
                "member_id": appointment.member.id,
                "practitioner_id": appointment.practitioner.id,
                "vertical_display_names": display_names,
                "created_at": appointment.created_at,
                "scheduled_start": appointment.scheduled_start,
                "scheduled_end": appointment.scheduled_end,
                "state": appointment.state,
                "member_started_at": appointment.member_started_at,
                "member_ended_at": appointment.member_ended_at,
                "practitioner_started_at": appointment.practitioner_started_at,
                "practitioner_ended_at": appointment.practitioner_ended_at,
                "cancelled_at": appointment.cancelled_at,
                "cancelled_by_user_id": appointment.cancelled_by_user_id,
                "anonymous": appointment.is_anonymous,
                "credit_spent": sum(c.amount for c in appointment.credits)
                if appointment.credits
                else None,
                "dollar_spent": appointment.payment.amount_captured
                if appointment.payment
                else None,
                "fee_paid": appointment.fee_paid,
                "fee_paid_at": appointment.fee_paid_at,
                "ratings": json.dumps(ratings),
                "credit_used_amounts": ",".join(
                    [str(c.amount) for c in appointment.credits]
                ),
                "credit_used_ids": ",".join(str(c.id) for c in appointment.credits),
                "codes_for_credits": ",".join(str(c) for c in codes_used),
                "comments": appointment.admin_comments,
                "booked_platform": platforms.get("booked"),
                "member_started_platform": platforms.get("member_started"),
                "code": appointment.user_recent_code,
            }
        )

        yield report.read_and_flush()


def all_invoices_csv():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return invoices_csv(Invoice.query.all())


def invoices_by_date_csv(start_datetime, end_datetime, distributed_providers_only=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    query = Invoice.query.filter(
        Invoice.created_at >= start_datetime, Invoice.created_at <= end_datetime
    )
    if distributed_providers_only:
        non_distributed_practitioner_ids = (
            db.session.query(PractitionerProfile.user_id)
            .join(PractitionerProfile.verticals)
            .join(
                PractitionerContract,
                PractitionerProfile.user_id == PractitionerContract.practitioner_id,
            )
            .filter(PractitionerContract.active == True)
            .filter(
                or_(
                    is_cx_vertical_name(Vertical.name),
                    PractitionerContract.emits_fees == False,
                )
            )
            .subquery()
        )

        practitioner = aliased(PractitionerProfile)
        invoices = (
            query.join(Invoice.entries)
            .outerjoin(
                FeeAccountingEntry.appointment,
                Appointment.product,
                FeeAccountingEntry.message,
                Message.channel,
                Channel.participants,
                ChannelUsers.user,
            )
            .outerjoin(practitioner, ChannelUsers.user_id == practitioner.user_id)
            .filter(
                or_(
                    Product.user_id.notin_(non_distributed_practitioner_ids),
                    practitioner.user_id.notin_(non_distributed_practitioner_ids),
                    FeeAccountingEntry.practitioner_id.notin_(
                        non_distributed_practitioner_ids
                    ),
                )
            )
            .all()
        )
    else:
        invoices = query.all()

    return invoices_csv(invoices)


def invoices_csv(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    invoices,
    fieldnames=[  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
        "status",
        "practitioner_id",
        "practitioner",
        "recipient_id",
        "transfer_id",
        "value",
        "id",
        "created_at",
        "started_at",
        "completed_at",
        "failed_at",
    ],
):
    report = GeneratorIO()
    writer = csv.DictWriter(report, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for invoice in sorted(invoices, key=lambda i: i.id):
        data = invoice.__dict__

        _email = None
        _prac_id = None
        if invoice.entries:
            for entry in invoice.entries:
                if entry.recipient:
                    _email = entry.recipient.email
                    _prac_id = entry.recipient.id
                    break
            else:
                log.info("No recipient for %s", invoice)
                continue

        if invoice.entries:
            data.update(
                {
                    "practitioner": _email,
                    "practitioner_id": _prac_id,
                    "value": invoice.value,
                }
            )

        writer.writerow(data)
        yield report.read_and_flush()


def failed_invoices_csv(invoices):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    report = GeneratorIO()
    fieldnames = [
        "Invoice ID",
        "Practitioner ID",
        "Practioner Email",
        "Amount Due",
        "Bank Account Status",
    ]
    writer = csv.DictWriter(report, fieldnames)
    writer.writeheader()
    for invoice in invoices:
        try:
            account_status = _get_account_status(invoice.practitioner)
        except Exception:
            log.exception("Error fetching bank account for invoice: %s", invoice)
            account_status = "error fetching bank account info"
        writer.writerow(
            {
                "Invoice ID": invoice.id,
                "Practitioner ID": invoice.practitioner.id,
                "Practioner Email": invoice.practitioner.email,
                "Amount Due": invoice.value,
                "Bank Account Status": account_status,
            }
        )
        yield report.read_and_flush()


def _get_account_status(practitioner):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client = StripeConnectClient(api_key=PAYMENTS_STRIPE_API_KEY)
    bank_account_info = client.get_bank_account_for_user(practitioner)
    if not bank_account_info:
        return "error fetching bank account info"
    return bank_account_info.status


def practitioner_fees_csv(start_datetime, end_datetime):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    all_fees = (
        db.session.query(FeeAccountingEntry)
        .filter(
            FeeAccountingEntry.created_at >= start_datetime,
            FeeAccountingEntry.created_at <= end_datetime,
        )
        .all()
    )
    return fees_csv(all_fees)


def fees_csv(fees):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    report = GeneratorIO()
    fieldnames = [
        "id",
        "created_at",
        "appointment_id",
        "appointment_status",
        "message_id",
        "practitioner_id",
        "practitioner_email",
        "product_price",
        "fee_amount",
        "invoice_id",
        "recipient_id",
        "transfer_id",
        "started_at",
        "completed_at",
        "failed_at",
    ]
    writer = csv.DictWriter(report, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for fee in fees:
        if fee.appointment_id:
            # video appointment
            appointment = fee.appointment
            appointment_id = appointment.id
            message_id = "N/A"
            practitioner_id = appointment.practitioner.id
            practitioner_email = appointment.practitioner.email
            appointment_status = fee.appointment.state
            product_price = fee.appointment.product.price
        elif fee.message_id:
            # messaging
            message = fee.message
            appointment_id = "N/A"
            message_id = message.id
            practitioner_email = message.channel.practitioner.email
            practitioner_id = message.channel.practitioner.id
            appointment_status = "N/A"
            try:
                product_price = message.credit.message_billing.message_product.price
            except AttributeError as e:
                log.debug("No product price for %s due to %s", fee, e)
                product_price = "N/A"
        else:
            appointment_id = "N/A"
            message_id = "N/A"
            appointment_status = "N/A"
            product_price = "N/A"
            if fee.practitioner:
                practitioner_id = fee.practitioner.id
                practitioner_email = fee.practitioner.email
            else:
                practitioner_id = "N/A"
                practitioner_email = "N/A"

        data = {
            "id": fee.id,
            "created_at": fee.created_at,
            "appointment_id": appointment_id,
            "appointment_status": appointment_status,
            "message_id": message_id,
            "practitioner_id": practitioner_id,
            "practitioner_email": practitioner_email,
            "product_price": product_price,
            "fee_amount": fee.amount,
            "invoice_id": fee.invoice_id,
        }

        if fee.invoice_id:
            data.update(
                {
                    "recipient_id": fee.invoice.recipient_id,
                    "transfer_id": fee.invoice.transfer_id,
                    "started_at": fee.invoice.started_at,
                    "completed_at": fee.invoice.completed_at,
                    "failed_at": fee.invoice.failed_at,
                }
            )

        writer.writerow(data)
        yield report.read_and_flush()


def messaging_report_csv(start, end):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    messages = (
        db.session.query(Message)
        .filter(Message.created_at >= start, Message.created_at <= end)
        .all()
    )

    report = GeneratorIO()
    fieldnames = [
        "id",
        "memberEmail",
        "memberID",
        "practitionerEmail",
        "practitionerID",
        "messageCreatedAt",
        "responseDeadline",
        "responseSentAt",
        "respondedWithinLimit",
        "responseID",
        "thankYouSent",
        "firstMessage",
        "practitionerFee",
        "relationshipID",
        "messageCounter",
    ]
    writer = csv.DictWriter(report, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for message in messages:
        try:
            c = message.credit
            respond_by = c.respond_by if c and c.respond_by else ""
            responded_at = c.responded_at if c and c.responded_at else ""
            responded_in_time = (
                True
                if c
                and c.responded_at
                and c.respond_by
                and c.responded_at <= c.respond_by
                else False
            )
            response_id = c.response_id if c else None
            ch_msgs = message.channel.messages
            member = message.channel.member
            practitioner = message.channel.practitioner
            data = {
                "id": message.id,
                "relationshipID": message.channel.id,
                "messageCounter": ch_msgs.index(message) + 1,
                "memberEmail": member and member.email,
                "memberID": member and member.id,
                "practitionerEmail": practitioner and practitioner.email,
                "practitionerID": practitioner and practitioner.id,
                "messageCreatedAt": message.created_at,
                "responseDeadline": respond_by,
                "responseSentAt": responded_at,
                "responseID": response_id,
                "respondedWithinLimit": responded_in_time,
                "thankYouSent": message.is_acknowledged_by(message.channel.member.id),
                "firstMessage": message.is_first_message_in_channel,
                "practitionerFee": sum(f.amount for f in message.fee),
            }
            writer.writerow(data)
            yield report.read_and_flush()
        except Exception as e:
            log.debug("Skipping %s due to exception: %s", message, e)
            continue
