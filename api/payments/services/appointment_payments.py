import datetime
from decimal import ROUND_HALF_UP, Decimal, getcontext
from typing import Optional, Tuple, Union

import sqlalchemy.orm
from stripe.error import StripeError

import payments.utils
from appointments.models.appointment import Appointment
from appointments.models.payments import Credit, PaymentAccountingEntry
from appointments.models.v2.cancel_appointment import CancellationPolicyStruct
from appointments.repository.v2.cancel_appointment import (
    MemberCancellationPolicyRepository,
)
from appointments.tasks.appointment_notifications import (
    send_practitioner_cancellation_note,
)
from appointments.utils.errors import (
    ErrorFetchingCancellationPolicy,
    ProductNotFoundException,
)
from models.products import Product
from utils.log import logger

getcontext().prec = 10

log = logger(__name__)


class AppointmentPaymentsService:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session
        self.cancellation_policy_repo = MemberCancellationPolicyRepository(self.session)

    def handle_cancel_appointment_by_practitioner_fees(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, appointment_id: int
    ):
        payment_accounting_entry = self.get_associated_payment_accounting_entry(
            appointment_id=appointment_id
        )
        if payment_accounting_entry:
            self.payment_accounting_entry_cancel(
                payment_accounting_entry=payment_accounting_entry
            )

        self.release_credits(appointment_id=appointment_id)

    def handle_cancel_appointment_by_member_fees(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        appointment_id: int,
        member_id: int,
        product_id: int,
        scheduled_start: datetime.datetime,
        product_price: Decimal,
        admin_initiated: bool,
    ):
        """
        We will look at the provider's cancellation policy, then charge the member the
        appropriate amount of money, consuming their available credits first before
        charging their card. We will also create fees for the provider.

        Currently, this should only be called in the case where a member is cancelling
        the appointment.
        """
        log.info(
            "Starting to handle cancel appointment fees",
            appointment_id=appointment_id,
            admin_initiated=admin_initiated,
        )
        # Use the provider's cancellation policy
        cancellation_policy_struct = (
            self.cancellation_policy_repo.get_cancellation_policy_struct(
                product_id=product_id
            )
        )

        if cancellation_policy_struct is None:
            raise ErrorFetchingCancellationPolicy(
                product_id=product_id, appointment_id=appointment_id
            )

        to_pay = self.get_payment_required_for_member_cancel_appointment(
            appointment_id=appointment_id,
            scheduled_start=scheduled_start,
            product_price=product_price,
            cancellation_policy=cancellation_policy_struct,
        )
        entry = None
        payment_accounting_entry = self.get_associated_payment_accounting_entry(
            appointment_id=appointment_id
        )
        if to_pay:
            balance = self.pay_with_reserved_credits(
                appointment_id=appointment_id,
                product_price=product_price,
                amount=to_pay,
            )
            if payment_accounting_entry:
                self.payment_accounting_entry_capture(
                    amount=balance, payment_accounting_entry=payment_accounting_entry
                )
            elif balance != 0:
                log.warning(
                    "Balance should be 0 for cancel appointment",
                    appointment_id=appointment_id,
                )
            entry = self.collect_practitioner_fees(
                appointment_id=appointment_id, to_pay=to_pay
            )
            log.info(
                "Captured payment for cancel appointment", appointment_id=appointment_id
            )
        else:
            if payment_accounting_entry:
                self.payment_accounting_entry_cancel(
                    payment_accounting_entry=payment_accounting_entry
                )
            log.info(
                "No payment required to cancel appointment",
                appointment_id=appointment_id,
                user_id=member_id,
            )
        self.release_credits(appointment_id=appointment_id)

        if not admin_initiated:
            practitioner_receives = str(entry.amount) if entry else str(0)
            send_practitioner_cancellation_note.delay(
                appointment_id, float(practitioner_receives), team_ns="virtual_care"
            )

    def get_associated_payment_accounting_entry(self, appointment_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            self.session.query(PaymentAccountingEntry)
            .filter(PaymentAccountingEntry.appointment_id == appointment_id)
            .first()
        )

    def pay_with_reserved_credits(
        self, appointment_id: int, product_price: Decimal, amount: Decimal = None  # type: ignore[assignment] # Incompatible default for argument "amount" (default has type "None", argument has type "Decimal")
    ) -> Decimal:
        # amount can be less than product price in the event of a cancellation
        amount = amount or product_price
        reserved = self.get_credits_reserved_for_appointment(
            appointment_id=appointment_id
        )

        total_credit = 0
        for credit in sorted(reserved, key=lambda x: x.amount, reverse=True):
            if total_credit >= amount:
                credit.appointment_id = None
                log.info(
                    "Releasing unnecessary credit",
                    credit_id=credit.id,
                    appointment_id=appointment_id,
                )
            elif (credit.amount + total_credit) > amount:
                credit, new_credit = self.split_credit_and_save_remaining_credit(
                    credit=credit,
                    amount_needed=Decimal(amount),
                    current_amount=Decimal(total_credit),
                )
                if new_credit:
                    log.info(
                        "Releasing unnecessary credit",
                        new_credit_id=new_credit.id,
                        appointment_id=appointment_id,
                    )
                credit.used_at = datetime.datetime.utcnow()
                total_credit += credit.amount
            elif (credit.amount + total_credit) <= amount:
                credit.used_at = datetime.datetime.utcnow()
                total_credit += credit.amount
            self.session.add(credit)

        self.session.commit()
        log.info(
            "Paying Appointment with credits.",
            total_credit=total_credit,
            amount=amount,
            appointment_id=appointment_id,
        )

        return Decimal(amount) - Decimal(total_credit)

    def get_credits_reserved_for_appointment(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            self.session.query(Credit)
            .filter(Credit.appointment_id == appointment_id)
            .order_by(Credit.amount.desc())
            .all()
        )

    def split_credit_and_save_remaining_credit(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, credit: Credit, amount_needed: Decimal, current_amount: Decimal
    ) -> Tuple[Credit, Optional[Credit]]:
        if amount_needed + current_amount >= credit.amount:
            log.warning(
                "Insufficient funds to split credit.",
                credit=credit,
                amount_needed=amount_needed,
                current_amount=current_amount,
            )
            return credit, None

        credit, new_credit = payments.utils.split_credit(
            credit=credit,
            updated_credit_amount=(amount_needed - current_amount),
        )
        self.session.add(new_credit)

        return credit, new_credit

    def release_credits(self, appointment_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        reserved = self.get_credits_reserved_for_appointment(
            appointment_id=appointment_id
        )
        i = 0

        for credit in reserved:
            if not credit.used_at:
                credit.appointment_id = None
                self.session.add(credit)
                i += 1

        log.info(
            "Released credits for appointment", credits=i, appointment_id=appointment_id
        )

    def payment_accounting_entry_capture(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, amount: Decimal, payment_accounting_entry: PaymentAccountingEntry
    ):
        if payment_accounting_entry:
            payment_accounting_entry.capture(amount=amount)

    def payment_accounting_entry_cancel(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, payment_accounting_entry: PaymentAccountingEntry
    ):
        if payment_accounting_entry:
            payment_accounting_entry.cancel()

    def get_payment_required_for_member_cancel_appointment(
        self,
        appointment_id: int,
        scheduled_start: datetime.datetime,
        product_price: Decimal,
        cancellation_policy: CancellationPolicyStruct,
        cancellation_datetime: datetime.datetime = None,  # type: ignore[assignment] # Incompatible default for argument "cancellation_datetime" (default has type "None", argument has type "datetime")
    ) -> Decimal:
        """
        Determines the cancellation payment amount for the appointment.
        Cancellation payment is computed based on cancellation time. If not provided through
        the cancellation_datetime arg, the default value is utcnow()
        This function ONLY applies to member cancellations. If the provider has cancelled, the member should not be paying for the appointment
        """
        if not cancellation_datetime:
            cancellation_datetime = datetime.datetime.utcnow()

        log.info(
            "Calculating cancellation payment amount for appointment",
            appointment_id=appointment_id,
            cancellation_policy_name=cancellation_policy.name,
            cancellation_datetime=str(cancellation_datetime),
        )

        refund_percent: int = 0

        if scheduled_start < cancellation_datetime:
            log.info(
                "No refund - appointment already started",
                appointment_id=appointment_id,
            )
        else:
            # determine the amount of the refund
            # note the values in the database have been used as the floor
            # (e.g. 6 < hrs <= 12 will use the refund_6_hours value to determine the refund)
            appointment_in = scheduled_start - cancellation_datetime

            seconds = 0
            if appointment_in.days:
                seconds = (60 * 60 * 24) * appointment_in.days
            seconds += appointment_in.seconds

            hours = seconds / (60 * 60)

            if 0 < hours <= 2:
                refund_percent = cancellation_policy.refund_0_hours or 0
            elif 2 < hours <= 6:
                refund_percent = cancellation_policy.refund_2_hours or 0
            elif 6 < hours <= 12:
                refund_percent = cancellation_policy.refund_6_hours or 0
            elif 12 < hours <= 24:
                refund_percent = cancellation_policy.refund_12_hours or 0
            elif 24 < hours <= 48:
                refund_percent = cancellation_policy.refund_24_hours or 0
            elif 48 < hours:
                refund_percent = cancellation_policy.refund_48_hours or 0

        pay_percent = abs(100 - refund_percent)
        pay_amount = product_price * Decimal(pay_percent) / 100
        pay_amount = pay_amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        log.info(
            "Original amount and refund amount",
            appointment_id=appointment_id,
            original_amount=product_price,
            refund_pay_amount=pay_amount,
        )
        return pay_amount

    # TODO (DISCO-3718): implemenet this method without using the appointment ORM
    def collect_practitioner_fees(self, appointment_id: int, to_pay: Decimal = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "to_pay" (default has type "None", argument has type "Decimal") #type: ignore[assignment] # Incompatible default for argument "to_pay" (default has type "None", argument has type "Decimal")
        appointmemt: Optional[Appointment] = (
            self.session.query(Appointment)
            .filter(Appointment.id == appointment_id)
            .first()
        )
        if appointmemt:
            return appointmemt.collect_practitioner_fees(price=to_pay)
        else:
            raise Exception("Appointment is not found.")

    def reserve_credits(
        self,
        appointment_id: int,
        product_id: int,
        member_id: int,
        scheduled_start: datetime.datetime,
    ) -> Decimal:
        """
        Does not commit to DB
        """
        available = Credit.available_for_member_time(
            member_id=member_id, scheduled_time=scheduled_start
        )
        product = self.session.query(Product).filter(Product.id == product_id).first()
        if product is None or product.price is None:
            log.error(f"product not found for product id {product_id}")
            raise ProductNotFoundException(product_id=product_id)
        price = product.price
        log.info(
            "Got price for Appointment",
            appointment_id=appointment_id,
            price=price,
            num_credits_available=len(available),
        )

        total_credit = Decimal(0)
        reserved = []
        available.reverse()

        while (total_credit < price) and available:
            credit = available.pop()

            if total_credit + credit.amount > price:
                log.info(
                    "Splitting Credit",
                    total_credit=total_credit,
                    credit=credit,
                    price=price,
                    appointment_id=appointment_id,
                )
                credit, new_credit = self.split_credit_and_save_remaining_credit(
                    credit=credit,
                    amount_needed=price,
                    current_amount=total_credit,
                )

            total_credit += credit.amount
            log.info(
                "Got total_credit",
                total_credit=total_credit,
                appointment_id=appointment_id,
            )

            credit.appointment_id = appointment_id
            reserved.append(credit)

            log.info(
                "Using credit",
                credit_id=credit.id,
                reserved_credit=credit,
                total_credit=total_credit,
                appointment_id=appointment_id,
                num_credits_available=len(available),
            )

        log.info(
            "Credits reserved for Appointment",
            credits_reserved=reserved,
            appointment_id=appointment_id,
            total_credit_reserved=total_credit,
            price=price,
            num_credits_available=len(available),
        )
        if reserved:
            self.session.add_all(reserved)

        # guarantee we never return a bad value here
        return max(Decimal(price - total_credit), Decimal(0))

    def authorize_payment(
        self,
        appointment_id: int,
        product_id: int,
        member_id: int,
        scheduled_start: datetime.datetime,
    ) -> Union[PaymentAccountingEntry, bool, None]:
        if appointment_id is None:
            log.error(
                "Attempted to authorize payment for a null appt-id!",
                product_id=product_id,
                member_id=member_id,
            )
            return None

        # If payment already exist for appointment, do not create a second one.
        pae = (
            self.session.query(PaymentAccountingEntry)
            .filter(PaymentAccountingEntry.appointment_id == appointment_id)
            .first()
        )

        if pae is not None and pae.stripe_id is not None:
            log.info(
                "Payment already authorized and created for appointments",
                payment_id=pae.id,
                appointment_id=appointment_id,
            )
            return pae

        balance = self.reserve_credits(
            appointment_id=appointment_id,
            product_id=product_id,
            member_id=member_id,
            scheduled_start=scheduled_start,
        )
        if balance:
            payment = PaymentAccountingEntry(
                appointment_id=appointment_id, amount=balance, member_id=member_id
            )

            payment = payment.authorize()
            if payment:
                self.session.add(payment)
                self.session.commit()
                log.info(
                    "Authorized payment for Appointment",
                    payment_id=payment.id,
                    appointment_id=appointment_id,
                )
                return payment
            else:
                log.warning(
                    "Could not auth payment for Appointment",
                    appointment_id=appointment_id,
                )
                return None
        else:
            log.info(
                "Paying in full with credits for Appointment",
                appointment_id=appointment_id,
            )
            return True

    def complete_payment(
        self, appointment_id: int, product_price: Decimal
    ) -> Tuple[bool, Union[int, None]]:
        balance = self.pay_with_reserved_credits(
            appointment_id=appointment_id, product_price=product_price
        )
        payment = self.get_associated_payment_accounting_entry(
            appointment_id=appointment_id
        )
        if payment:
            if balance != payment.amount:
                log.warning(
                    "Appointment balance changed before payment completion!",
                    appointment_id=appointment_id,
                    appointment_balance=payment.amount,
                    new_balance=balance,
                )
                return False, None

            try:
                amount = payment.capture(amount=balance)
            except StripeError as e:
                log.warning(
                    "Could not capture stripe payment.",
                    appointment_id=appointment_id,
                    balance=balance,
                )
                raise e

            if amount:
                log.info("Appointment payment captured.", appointment_id=appointment_id)
                return True, amount
            else:
                log.warning(
                    "Unknown problem capturing appointment payment.",
                    appointment_id=appointment_id,
                    balance=balance,
                )
        elif balance <= 0:
            log.info(
                "Appointment paid in full with credits!", appointment_id=appointment_id
            )
            return True, None
        else:
            log.warning(
                "Appointment with no payment and outstanding balance.",
                appointment_id=appointment_id,
            )
        return False, None
