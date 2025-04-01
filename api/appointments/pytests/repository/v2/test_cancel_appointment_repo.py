import datetime
import json
from decimal import Decimal

from appointments.models.appointment import Appointment
from appointments.repository.v2.cancel_appointment import CancelAppointmentRepository
from pytests.freezegun import freeze_time
from storage.connection import db


class TestCancelAppointmentRepository:
    def test_get_cancel_appointment_struct_by_id(
        self, factories, enterprise_user, datetime_now
    ):
        vertical = factories.VerticalFactory.create(products=None)
        product = factories.ProductFactory(
            vertical=vertical,
            minutes=30,
            price=2.0,
        )
        member_schedule = factories.ScheduleFactory.create(
            user=enterprise_user, user_id=enterprise_user.id
        )
        appointment = factories.AppointmentFactory.create(
            scheduled_start=datetime_now,
            member_schedule_id=member_schedule.id,
            member_schedule=member_schedule,
            product_id=product.id,
            product=product,
        )

        result = CancelAppointmentRepository(
            db.session
        ).get_cancel_appointment_struct_by_id(appointment.id)

        assert result.id == appointment.id
        assert result.scheduled_start == datetime_now
        assert result.cancelled_at is None
        assert result.member_id == enterprise_user.id
        assert result.practitioner_id == product.user_id
        assert result.product_price == Decimal(2.0)

    def test_update_appointment_for_cancel(self, factories, enterprise_user):
        appointment = factories.AppointmentFactory.create()
        expected_json_dict = {"cancelled_note": "test"}
        json_str = json.dumps(expected_json_dict)

        with freeze_time("2023-11-16", tick=False):
            CancelAppointmentRepository(db.session).update_appointment_for_cancel(
                appointment_id=appointment.id,
                user_id=enterprise_user.id,
                json_str=json_str,
            )

            db.session.expire_all()
            appointment = (
                db.session.query(Appointment)
                .filter(Appointment.id == appointment.id)
                .one()
            )
            assert appointment.cancelled_at is not None
            assert appointment.cancelled_by_user_id == enterprise_user.id
            assert appointment.json == expected_json_dict
            assert appointment.modified_at == datetime.datetime.utcnow()

    def test_get_cancelled_by_user_id(self, factories, enterprise_user, datetime_now):
        vertical = factories.VerticalFactory.create(products=None)
        product = factories.ProductFactory(
            vertical=vertical,
            minutes=30,
            price=2.0,
        )
        member_schedule = factories.ScheduleFactory.create(
            user=enterprise_user, user_id=enterprise_user.id
        )
        appointment = factories.AppointmentFactory.create(
            scheduled_start=datetime_now,
            member_schedule_id=member_schedule.id,
            member_schedule=member_schedule,
            product_id=product.id,
            product=product,
            cancelled_by_user_id=enterprise_user.id,
        )

        result = CancelAppointmentRepository(db.session).get_cancelled_by_user_id(
            appointment.id
        )

        assert result == appointment.cancelled_by_user_id
