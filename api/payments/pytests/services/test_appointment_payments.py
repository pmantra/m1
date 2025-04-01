from decimal import Decimal

from appointments.models.payments import Credit
from appointments.models.v2.cancel_appointment import CancellationPolicyStruct
from appointments.pytests.factories import PaymentAccountingEntryFactory
from payments.services.appointment_payments import AppointmentPaymentsService
from pytests import factories
from pytests.db_util import enable_db_performance_warnings
from storage.connection import db


# TODO(DISCO-3818): add more unit tests for higher coverage.
class TestAppointmentPaymentService:
    def test_get_associated_payment_accounting_entry_true(self):
        appointment = factories.AppointmentFactory.create()
        payment_accounting_entry = PaymentAccountingEntryFactory.create(
            appointment_id=appointment.id
        )

        result = AppointmentPaymentsService(
            db.session
        ).get_associated_payment_accounting_entry(appointment_id=appointment.id)

        assert result == payment_accounting_entry

    def test_get_associated_payment_accounting_entry_false(self):
        appointment = factories.AppointmentFactory.create()

        result = AppointmentPaymentsService(
            db.session
        ).get_associated_payment_accounting_entry(appointment_id=appointment.id)

        assert result is None

    def test_get_credits_reserved_for_appointment(self, new_credit):
        appointment = factories.AppointmentFactory.create()
        user = factories.EnterpriseUserFactory.create()
        new_credit(amount=10, appointment_id=appointment.id, user=user)
        new_credit(amount=5, appointment_id=appointment.id, user=user)
        new_credit(amount=8, appointment_id=None, user=user)

        credits = AppointmentPaymentsService(
            db.session
        ).get_credits_reserved_for_appointment(appointment_id=appointment.id)

        assert len(credits) == 2
        assert credits[0].amount == 10
        assert credits[1].amount == 5

    def test_release_credits(self, new_credit, yesterday):
        appointment = factories.AppointmentFactory.create()
        user = factories.EnterpriseUserFactory.create()
        credit1 = new_credit(amount=10, appointment_id=appointment.id, user=user)
        new_credit(
            amount=5, appointment_id=appointment.id, used_at=yesterday, user=user
        )

        AppointmentPaymentsService(db.session).release_credits(
            appointment_id=appointment.id
        )

        assert (
            db.session.query(Credit)
            .filter(Credit.id == credit1.id)
            .one()
            .appointment_id
            is None
        )

    def test_pay_with_reserved_credits(self, new_credit):
        appointment = factories.AppointmentFactory.create()
        user = factories.EnterpriseUserFactory.create()
        new_credit(amount=15, appointment_id=appointment.id, user=user)

        result = AppointmentPaymentsService(db.session).pay_with_reserved_credits(
            appointment_id=appointment.id, product_price=Decimal(3), amount=Decimal(4)
        )

        credit = (
            db.session.query(Credit)
            .filter(Credit.appointment_id == appointment.id)
            .one()
        )
        assert result == 0
        assert credit.amount == 4

    def test_get_payment_required_for_member_cancel_appointment(
        self, enterprise_user, datetime_one_hour_earlier
    ):
        appointment = factories.AppointmentFactory.create()
        vertical = factories.VerticalFactory.create(products=None)
        product = factories.ProductFactory(
            vertical=vertical,
            minutes=30,
            price=2.0,
        )
        cancellation_policy_struct = CancellationPolicyStruct(
            id=1,
            name="flexible",
            refund_0_hours=0,
            refund_2_hours=0,
            refund_6_hours=0,
            refund_12_hours=0,
            refund_24_hours=100,
            refund_48_hours=100,
        )

        with enable_db_performance_warnings(
            database=db,
            # warning_threshold=1,  # uncomment to view all queries being made
            failure_threshold=1,
        ):
            pay_amount = AppointmentPaymentsService(
                db.session
            ).get_payment_required_for_member_cancel_appointment(
                appointment_id=appointment.id,
                scheduled_start=datetime_one_hour_earlier,
                product_price=Decimal(product.price),
                cancellation_policy=cancellation_policy_struct,
            )

        assert pay_amount == Decimal(2)

    def test_handle_cancel_appointment_fees(
        self, new_credit, enterprise_user, datetime_one_hour_earlier
    ):
        appointment = factories.AppointmentFactory.create()
        practitioner = factories.PractitionerUserFactory.create()
        practitioner.practitioner_profile.cancellation_policy
        vertical = factories.VerticalFactory.create(products=None)
        product = factories.ProductFactory(
            vertical=vertical,
            minutes=30,
            price=2.0,
        )
        PaymentAccountingEntryFactory.create(appointment_id=appointment.id)
        # set up reserved credit
        credit = new_credit(
            amount=2, appointment_id=appointment.id, user=enterprise_user
        )

        with enable_db_performance_warnings(
            database=db,
            # warning_threshold=13,  # uncomment to view all queries being made
            failure_threshold=13,
        ):
            AppointmentPaymentsService(
                db.session
            ).handle_cancel_appointment_by_member_fees(
                appointment_id=appointment.id,
                member_id=enterprise_user.id,
                product_id=product.id,
                scheduled_start=datetime_one_hour_earlier,
                product_price=Decimal(2.0),
                admin_initiated=False,
            )

        paid_credit = db.session.query(Credit).filter(Credit.id == credit.id).one()
        assert paid_credit.used_at is not None
