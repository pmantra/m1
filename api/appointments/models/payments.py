from __future__ import annotations

import datetime
import enum
import json
from decimal import Decimal
from typing import Optional

import ddtrace
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    bindparam,
    func,
    literal_column,
)
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.orm import backref, relationship

from authn.models.user import User
from common import stats
from common.services.stripe import StripeCustomerClient, StripeTransferClient
from common.services.stripe_constants import (
    PAYMENTS_STRIPE_API_KEY,
    STRIPE_ACTION_TYPES,
)
from models import base
from models.actions import audit
from payments.models.constants import PROVIDER_PAYMENTS_EMAIL
from storage.connection import db
from utils.data import JSONAlchemy
from utils.log import logger
from utils.mail import alert_admin

log = logger(__name__)

MONEY_PRECISION = 8

practitioner_credits = db.Table(
    "practitioner_credits",
    Column("user_id", Integer, ForeignKey("practitioner_profile.user_id")),
    Column("credit_id", Integer, ForeignKey("credit.id")),
    UniqueConstraint("user_id", "credit_id"),
)

user_practitioner_billing_rules = db.Table(
    "user_practitioner_billing_rules",
    Column("user_id", Integer, ForeignKey("user.id")),
    Column(
        "appointmet_fee_creator_id", Integer, ForeignKey("appointmet_fee_creator.id")
    ),
    UniqueConstraint("user_id", "appointmet_fee_creator_id"),
)


class RECIPIENT_TYPES:
    corporation = "corporation"
    individual = "individual"


def new_stripe_customer(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)
    customer = client.create_customer_for_user(user)
    if customer:
        return customer.get("id")


class Credit(base.TimeLoggedModelBase):
    __tablename__ = "credit"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", uselist=False, backref="credits")
    amount = Column(DOUBLE(precision=MONEY_PRECISION, scale=2))

    activated_at = Column(DateTime(), nullable=True)
    used_at = Column(DateTime(), nullable=True)
    expires_at = Column(DateTime(), nullable=True)
    practitioners = relationship(
        "PractitionerProfile", backref="client_credits", secondary=practitioner_credits
    )

    appointment_id = Column(Integer, ForeignKey("appointment.id"), nullable=True)
    appointment = relationship("Appointment", uselist=False, backref="credits")

    referral_code_use_id = Column(
        Integer, ForeignKey("referral_code_use.id"), nullable=True
    )
    referral_code_use = relationship(
        "ReferralCodeUse", uselist=False, backref="credits"
    )

    message_billing_id = Column(
        Integer, ForeignKey("message_billing.id"), nullable=True
    )
    message_billing = relationship(
        "MessageBilling", uselist=False, backref=backref("credits")
    )
    json = Column(JSONAlchemy(Text(100)), default={})

    eligibility_member_id = Column(Integer, nullable=True)
    eligibility_verification_id = Column(Integer, nullable=True)
    eligibility_member_2_id = Column(Integer, nullable=True)
    eligibility_member_2_version = Column(Integer, nullable=True)
    eligibility_verification_2_id = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<Credit (ID: {self.id}) [${self.amount} - Reserved for {self.appointment_id}]>"

    __str__ = __repr__

    @classmethod
    @ddtrace.tracer.wrap()
    def available_for_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return cls.available_for_user_id(user_id=user.id)

    @classmethod
    def available_for_user_id(cls, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        now = datetime.datetime.utcnow().replace(microsecond=0)
        credits = db.session.query(cls).filter(
            cls.user_id == user_id,
            ((cls.expires_at >= now) | (cls.expires_at.is_(None))),
            ((cls.activated_at <= now) | (cls.activated_at.is_(None))),
            cls.appointment_id.is_(None),
            cls.used_at.is_(None),
            cls.message_billing_id.is_(None),
        )
        return credits

    @classmethod
    def available_amount_for_user_id(cls, user_id: int) -> int:
        query = db.session.query(
            func.coalesce(func.sum(cls.amount), literal_column("0"))
        ).filter(
            cls.user_id == bindparam("user_id"),
            # Only records which are active and not expired
            #   default to `NOW()` on the server.
            func.coalesce(cls.expires_at, func.now()) >= func.now(),
            func.coalesce(cls.activated_at, func.now()) <= func.now(),
            # Not set aside for an appointment.
            cls.appointment_id.is_(None),
            # Not already used.
            cls.used_at.is_(None),
            # Not associated to a message.
            cls.message_billing_id.is_(None),
        )
        return query.params(user_id=user_id).scalar()

    @classmethod
    @ddtrace.tracer.wrap()
    def available_amount_for_user(cls, user: User) -> int:
        return sum(c.amount for c in cls.available_for_user(user).all())

    @classmethod
    def available_for_appointment(cls, appointment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return cls.available_for_member_time(
            appointment.member.id, appointment.scheduled_start
        )

    @classmethod
    def available_for_member_time(cls, member_id, scheduled_time):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # TODO: this logic should be extracted
        active_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)

        unreserved_credits = db.session.query(cls).filter(
            cls.appointment_id == None,
            cls.used_at == None,
            cls.user_id == member_id,
            ((cls.activated_at <= active_time) | (cls.activated_at == None)),
            ((cls.expires_at >= scheduled_time) | (cls.expires_at == None)),
        )

        unreserved_credits = unreserved_credits.order_by(
            cls.expires_at.desc()
        ).order_by(cls.amount.desc())

        unreserved_credits = unreserved_credits.all()
        return unreserved_credits

    @classmethod
    def reserved_for_appointment(cls, appointment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            db.session.query(cls)
            .filter(cls.appointment_id == appointment.id)
            .order_by(cls.amount.desc())
            .all()
        )

    @classmethod
    def expire_all_enterprise_credits_for_user(
        cls,
        user_id: int | None,
        expires_at: datetime.datetime,
    ) -> None:
        db.session.query(Credit).filter(
            cls.user_id == user_id,
            (
                cls.eligibility_member_id.isnot(None)
                | cls.eligibility_verification_id.isnot(None)
                | cls.eligibility_member_2_id.isnot(None)
                | cls.eligibility_member_2_version.isnot(None)
                | cls.eligibility_verification_2_id.isnot(None)
            ),
        ).update({"expires_at": expires_at})

    def split_excess(self, amount_needed):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info("Splitting %s into new and old credits", self)
        amount_needed = Decimal(amount_needed)

        new_credit = None
        excess = self.amount - amount_needed
        if excess:
            new_credit = self.copy_with_excess(excess)
            db.session.add(new_credit)
            self.amount = amount_needed

        return self, new_credit

    def copy_with_excess(self, excess):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        new = self.__class__(
            user=self.user,
            amount=excess,
            activated_at=self.activated_at,
            expires_at=self.expires_at,
            referral_code_use_id=self.referral_code_use_id,
            eligibility_member_id=self.eligibility_member_id,
            eligibility_verification_id=self.eligibility_verification_id,
            eligibility_member_2_id=self.eligibility_member_2_id,
            eligibility_member_2_version=self.eligibility_member_2_version,
            eligibility_verification_2_id=self.eligibility_verification_2_id,
            json={"excess_from": self.id},
        )

        new.practitioners.extend(self.practitioners)
        log.debug(f"Added {new}")
        return new


class PaymentAccountingEntry(base.TimeLoggedModelBase):
    __tablename__ = "payment_accounting_entry"

    id = Column(Integer, primary_key=True)
    amount = Column(DOUBLE(precision=MONEY_PRECISION, scale=2), nullable=False)
    amount_captured = Column(DOUBLE(precision=MONEY_PRECISION, scale=2))

    appointment_id = Column(Integer, nullable=False)

    member_id = Column(Integer, nullable=True)

    stripe_id = Column(String(255))
    captured_at = Column(DateTime(), nullable=True)
    cancelled_at = Column(DateTime(), nullable=True)

    def __repr__(self) -> str:
        return f"<PaymentAccountingEntry (ID: {self.id}) [{self.amount} ({bool(self.stripe_id)} - {self.captured_at})]>"

    __str__ = __repr__

    @property
    def appointment(self):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.models.appointment import Appointment

        appointmemt: Optional[Appointment] = (
            db.session.query(Appointment)
            .filter(Appointment.id == self.appointment_id)
            .first()
        )
        if appointmemt:
            return appointmemt
        else:
            raise Exception("Cannot find appointment from PaymentAccountingEntry")

    @property
    def member(self) -> User:
        # When member_id is present, find the user with member id
        # Otherwise fall back to appointment member
        if self.member_id:
            return db.session.query(User).filter(User.id == self.member_id).one()
        return self.appointment.member

    def authorize(self, member=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        member = member or self.member

        stripe_client = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)
        cards = stripe_client.list_cards(user=member)
        if not cards:
            log.info("No cards for %s - not authorizing", member.id)
            return

        charge = stripe_client.create_charge(amount_in_dollars=self.amount, user=member)
        if charge:
            self.stripe_id = charge.id
            return self
        else:
            log.warning("Stripe charge creation failed! Cannot auth %s", self)

    def capture(self, amount=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        stripe_client = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)

        if self.is_captured:
            log.info(f"{self} is already captured, not capturing...")
            return self.amount_captured * 100
        if amount is None:
            log.info("Need an amount to capture! Returning...")
            return

        log.info(f"Capturing ${amount} for {self}")
        charge = stripe_client.capture_charge(
            user=self.member,
            stripe_charge_id=self.stripe_id,
            amount_in_dollars=amount,
        )
        if charge:
            self.stripe_id = charge.stripe_id
            self.captured_at = datetime.datetime.utcnow()
            self.amount_captured = charge.amount / 100
            db.session.add(self)
            log.info(f"Captured {self}")
            return self.amount_captured
        else:
            log.warning("Could not capture %s", self)

    def cancel(self, skip_commit=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info(f"Cancelling {self}")
        stripe_client = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)
        refund = stripe_client.refund_charge(stripe_charge_id=self.stripe_id)
        if refund:
            self.cancelled_at = datetime.datetime.utcnow()
            db.session.add(self)
            if skip_commit:
                db.session.flush()
            else:
                db.session.commit()
            log.info("Cancelled %s", self)
        else:
            log.warning("Could not refund %s", self)

    def swap_for_new_charge(self, amount=None, capture: bool = False) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.is_captured:
            log.info("%s already captured - not swapping...", self)
            return

        log.info(f"Re-charging payments for {self}")
        stripe_client = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)
        new_charge = stripe_client.create_charge(
            amount_in_dollars=amount or self.amount,
            user=self.member,
            capture=capture,
        )
        if new_charge:
            log.info(f"Got new charge for {self}")
            audit(
                "payment_swap_stripe_id",
                user_id=self.member.id,
                old_id=self.stripe_id,
                old_amount_captured=str(self.amount_captured),
                old_cancelled_at=str(self.cancelled_at),
                old_captured_at=str(self.captured_at),
            )

            self.stripe_id = new_charge.id
            if capture:
                self.captured_at = datetime.datetime.utcnow()
                self.amount_captured = new_charge.amount / 100
            else:
                self.captured_at = None
                self.amount_captured = None

            self.cancelled_at = None
            db.session.add(self)
            db.session.commit()
        else:
            log.info("Problem making new charge for %s", self)

        log.info("All set swapping new charge for %s", self)

    @property
    def is_captured(self) -> bool:
        return bool(self.captured_at or self.amount_captured)

    @classmethod
    def retain_data_for_user(cls, user: User) -> bool:
        return any(
            a.payment is not None and a.payment.is_captured
            for a in user.schedule.appointments
        )


class FeeAccountingEntryTypes(str, enum.Enum):
    APPOINTMENT = "APPOINTMENT"
    MESSAGE = "MESSAGE"
    ONE_OFF = "ONE OFF"
    MALPRACTICE = "MALPRACTICE"
    NON_STANDARD_HOURLY = "NON STANDARD HOURLY"
    UNKNOWN = "UNKNOWN"


class FeeAccountingEntry(base.TimeLoggedModelBase):
    __tablename__ = "fee_accounting_entry"
    id = Column(Integer, primary_key=True)

    amount = Column(DOUBLE(precision=MONEY_PRECISION, scale=2))

    appointment_id = Column(Integer, ForeignKey("appointment.id"), nullable=True)
    appointment = relationship("Appointment", backref="fees")

    invoice_id = Column(Integer, ForeignKey("invoice.id"), nullable=True)
    invoice = relationship("Invoice", uselist=False, backref="entries")

    message_id = Column(Integer, ForeignKey("message.id"), nullable=True)
    message = relationship("Message", uselist=False, backref="fee")

    practitioner_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    practitioner = relationship("User", backref="administrative_fees")

    type = Column(Enum(FeeAccountingEntryTypes, native_enum=False), nullable=False)

    def __repr__(self) -> str:
        return f"<FeeAccountingEntry[{self.id}] [Appt {self.appointment_id}/Msg {self.message_id}/Prac {self.practitioner_id} - ${self.amount}]>"

    __str__ = __repr__

    @property
    def recipient(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.appointment:
            recipient = self.appointment.product.practitioner
        elif self.message and self.message.channel:
            recipient = self.message.channel.practitioner
        elif self.practitioner:
            recipient = self.practitioner
        else:
            log.warning("%s has neither appointment nor message", self)
            return
        return recipient

    @property
    def stripe_recipient_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        recipient = self.recipient

        if recipient:
            entry_recipient = recipient.practitioner_profile.stripe_account_id
            return entry_recipient


class StartTransferErrorMsg(enum.Enum):
    NO_ENTRIES = "No fees for invoice"
    NO_RECIPIENTS = "No recipients. Cannot transfer"
    MORE_THAN_ONE_RECIPIENTS = "More than one recipients. Cannot transfer"
    VALUE_IS_ZERO = "Cannot start a transfer with no value"
    VALUE_IS_NEGATIVE = "Cannot transfer a negative amount"
    EXISTING_TRANSFER_ID = "Invoice already has a transfer ID!"
    INVOICE_ALREADY_STARTED = "Invoice already started!"
    INVOICE_ALREADY_FAILED = "Invoice already failed!"
    INVOICE_ALREADY_COMPLETED = "Invoice already complete!"
    UNSUCCESSFUL_STRIPE_TRANSFER = "Could not start transfer for invoice"


class Invoice(base.TimeLoggedModelBase):
    __tablename__ = "invoice"

    id = Column(Integer, primary_key=True)
    # any reason why this is not nullable where other stripe id columns are?
    recipient_id = Column(String(255), nullable=False)
    transfer_id = Column(String(255))

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    json = Column(JSONAlchemy(Text(1000)), default={})

    def __repr__(self) -> str:
        return f"<Invoice {self.id} (Started @ {self.started_at})>"

    __str__ = __repr__

    @property
    def value(self) -> int:
        return sum(entry.amount for entry in self.entries)

    @property
    def practitioner(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        practitioners = set()
        for e in self.entries:
            if e.appointment:
                practitioners.add(e.appointment.practitioner)
            elif e.message and e.message.channel:
                practitioners.add(e.message.channel.practitioner)
            elif e.practitioner:
                practitioners.add(e.practitioner)
            else:
                log.warning("%s has neither appointment nor message", e)
                return

        if len(practitioners) > 1:
            log.warning("Not consistent practitioners for %s!", self)
            return
        return practitioners.pop() if practitioners else None

    def add_entry(self, entry):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Use this to add entries instead of setting invoice_id on
        FeeAccountingEntry directly.
        """
        entry_recipient = entry.stripe_recipient_id

        if not entry_recipient:
            log.info(
                "Cannot add entry to invoice -- entry has no recipient",
                entry=entry,
                invoice=self,
            )
            return

        # Detect if entry already belongs to an invoice
        if entry.invoice_id:
            if entry.invoice_id != self.id:
                log.warning(
                    "Cannot add entry to invoice -- entry already belongs to a different invoice",
                    entry_id=entry.id,
                    invoice_id=self.id,
                    entry_invoice_id=entry.invoice.id,
                )

            else:
                log.info(
                    "Cannot add entry to invoice -- entry already belongs to this invoice",
                    entry_id=entry.id,
                    invoice_id=self.id,
                    entry_invoice_id=entry.invoice.id,
                )

            return

        if self.recipient_id is not None:
            if entry_recipient == self.recipient_id:
                self.entries.append(entry)
                log.info(
                    "Added entry to invoice",
                    entry_id=entry.id,
                    invoice_id=self.id,
                )
            else:
                log.info(
                    "Cannot add entry to invoice -- wrong recipient!",
                    entry_id=entry.id,
                    invoice_id=self.id,
                )
        else:
            self.recipient_id = entry_recipient
            self.entries.append(entry)
            log.info(
                "Added entry to invoice (case where entry Invoice did not have recipient_id)",
                entry_id=entry.id,
                invoice_id=self.id,
            )

        return entry

    def _validate_not_already_existing_started_failed_or_completed(self) -> None:
        if self.transfer_id:
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:has_transfer_id"],
            )
            log.warning(
                StartTransferErrorMsg.EXISTING_TRANSFER_ID.value, invoice=self.id
            )
            raise Exception(StartTransferErrorMsg.EXISTING_TRANSFER_ID.value)

        if self.started_at:
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:has_started_at"],
            )
            log.warning(
                StartTransferErrorMsg.INVOICE_ALREADY_STARTED.value, invoice=self.id
            )
            raise Exception(StartTransferErrorMsg.INVOICE_ALREADY_STARTED.value)

        if self.failed_at:
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:has_failed_at"],
            )
            log.warning(
                StartTransferErrorMsg.INVOICE_ALREADY_FAILED.value, invoice=self.id
            )
            raise Exception(StartTransferErrorMsg.INVOICE_ALREADY_FAILED.value)

        if self.completed_at:
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:has_completed_at"],
            )
            log.warning(
                StartTransferErrorMsg.INVOICE_ALREADY_COMPLETED.value, invoice=self.id
            )
            raise Exception(StartTransferErrorMsg.INVOICE_ALREADY_COMPLETED.value)

    def _validate_value_not_none_nor_negative(self) -> None:
        if self.value in (0, None, ""):
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:no_value"],
            )
            log.warning(StartTransferErrorMsg.VALUE_IS_ZERO.value, invoice=self.id)
            raise Exception(StartTransferErrorMsg.VALUE_IS_ZERO.value)

        if (self.value not in (0, None)) and (self.value < 0):
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:negative_amount"],
            )
            log.warning(StartTransferErrorMsg.VALUE_IS_NEGATIVE.value, invoice=self.id)
            raise Exception(StartTransferErrorMsg.VALUE_IS_NEGATIVE.value)

    def _validate_has_entries(self) -> None:
        if not self.entries:
            log.warning(StartTransferErrorMsg.NO_ENTRIES.value, invoice=self.id)
            raise Exception(StartTransferErrorMsg.NO_ENTRIES.value)

    def _validate_one_recipient(self) -> None:
        recipients_stripe_ids = {
            e.stripe_recipient_id
            for e in self.entries
            if e.stripe_recipient_id is not None
        }

        if len(recipients_stripe_ids) == 0:
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:inconsistent_recipients"],
            )
            log.warning(StartTransferErrorMsg.NO_RECIPIENTS.value, invoice=self.id)
            raise Exception(StartTransferErrorMsg.NO_RECIPIENTS.value)

        if len(recipients_stripe_ids) > 1:
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:inconsistent_recipients"],
            )
            log.warning(
                StartTransferErrorMsg.MORE_THAN_ONE_RECIPIENTS.value, invoice=self.id
            )
            raise Exception(StartTransferErrorMsg.MORE_THAN_ONE_RECIPIENTS.value)

    def start_transfer(self) -> None:
        # The order of these validations does not matter in terms of logic. Nontheless, this order is taken into account for testing, so it must be preserved unless tests are changed. See test_start_transfer.py
        self._validate_not_already_existing_started_failed_or_completed()

        self._validate_has_entries()

        self._validate_one_recipient()

        # Update the invoice's recipient_id in case the provider has updated their bank account information
        if (
            self.recipient_id
            != self.practitioner.practitioner_profile.stripe_account_id
        ):
            self.recipient_id = self.practitioner.practitioner_profile.stripe_account_id
            db.session.add(self)
            db.session.commit()

        self._validate_value_not_none_nor_negative()

        stripe = StripeTransferClient(PAYMENTS_STRIPE_API_KEY)
        log.info("Starting transfer for invoice", invoice=self.id)
        user = self.practitioner
        transfer = stripe.start_transfer(
            stripe_account_id=self.recipient_id,
            amount_in_dollars=self.value,
            user_id=user.id if user else None,
            invoice_id=self.id,
        )
        if transfer:
            try:
                self.transfer_id = transfer.id
                self.started_at = datetime.datetime.utcnow()
                self.json["transfer_at_creation"] = json.dumps(transfer)
                log.info(
                    "Transfer successful and updating invoice", transfer_id=transfer.id
                )
            except Exception as e:
                log.error(
                    "Exception in setting the invoice data.",
                    exception=str(e),
                )
        else:
            stats.increment(
                metric_name="api.models.payments.invoice.start_transfer",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=["error:true", "error_cause:failed_to_start"],
            )
            log.warning(
                StartTransferErrorMsg.UNSUCCESSFUL_STRIPE_TRANSFER.value,
                invoice=self.id,
            )
            raise Exception(StartTransferErrorMsg.UNSUCCESSFUL_STRIPE_TRANSFER.value)

    def close_invoice(self) -> bool:
        if self.started_at is not None:
            return False
        self.started_at = datetime.datetime.utcnow()
        self.completed_at = datetime.datetime.utcnow()
        self.transfer_id = "CLOSED MANUALLY"
        return True

    def confirm_payout_failure(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        invoice = self._confirm_transfer_webhook(
            "failed", "failed_at", STRIPE_ACTION_TYPES.transfer_completion_failed
        )

        text = f"Transfer for {self} has failed!"
        subject = f"Failed Transfer at: {datetime.datetime.utcnow()}"
        alert_emails = [PROVIDER_PAYMENTS_EMAIL]
        alert_admin(text, alert_emails, subject)

        return invoice

    def confirm_payout_success(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        invoice = self._confirm_transfer_webhook(
            "paid", "completed_at", STRIPE_ACTION_TYPES.transfer_completion_succeeded
        )
        return invoice

    def _confirm_transfer_webhook(self, status, attr, action):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if getattr(self, attr):
            log.info("%s already has attr: %s", self, attr)
            return

        setattr(self, attr, datetime.datetime.utcnow())
        db.session.add(self)

        self._log_to_audit(action)

        return self

    def _log_to_audit(self, action):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info("audit_log_events", audit_log_info={"action_type": action})


class AppointmentFeeCreator(base.TimeLoggedModelBase):
    __tablename__ = "appointmet_fee_creator"

    id = Column(Integer, primary_key=True)
    fee_percentage = Column(Integer)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    practitioner = relationship("User", uselist=False)
    members = relationship("User", secondary=user_practitioner_billing_rules)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AppointmentFeeCreator [Practitioner {self.user_id} @ {self.fee_percentage} - ({self.valid_from} to {self.valid_to})]>"

    __str__ = __repr__

    @classmethod
    def for_appointment(cls, appointment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for_member_in_dates = db.session.query(cls).filter(
            ((cls.user_id == appointment.practitioner.id) | (cls.user_id == None))
            & (
                (cls.valid_from == None)
                | (cls.valid_from <= appointment.scheduled_start)
            )
            & ((cls.valid_to == None) | (cls.valid_to >= appointment.scheduled_end))
            & (cls.members.any(User.id == appointment.member.id) | ~cls.members.any())
        )

        if for_member_in_dates.all():
            in_order = sorted(
                for_member_in_dates, key=lambda x: x.fee_percentage, reverse=True
            )
            log.info(f"Highest fee creator is: {in_order[0]}")
            return in_order[0]
        else:
            log.info("Returning default AFC")
            return cls(fee_percentage=70)
