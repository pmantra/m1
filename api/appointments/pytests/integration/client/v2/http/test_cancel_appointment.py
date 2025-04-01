from datetime import datetime, timedelta

from appointments.models.appointment import Appointment
from appointments.services.common import obfuscate_appointment_id
from storage.connection import db


class TestCancelAppointment:
    def test_post_cancel_from_member(
        self, client, api_helpers, factories, enterprise_user
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
            scheduled_start=datetime.utcnow() + timedelta(minutes=20),
            member_schedule_id=member_schedule.id,
            member_schedule=member_schedule,
            product_id=product.id,
            product=product,
        )
        obfuscated_appt_id = obfuscate_appointment_id(appointment.id)

        res = client.post(
            f"/api/v2/appointments/{obfuscated_appt_id}/cancel",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({}),
        )

        assert res.status_code == 200
        data = res.json
        assert data["id"] == obfuscated_appt_id
        assert data["state"] == "CANCELLED"
        assert data["product_id"] == product.id
        assert data["survey_types"] == [
            "cancellation_survey",
            "member_rating_v2",
            "member_rating_followup_v2",
        ]
        assert data["provider"]["id"] == product.user_id
        assert data["cancelled_at"] is not None

    def test_post_cancel_twice_from_member(
        self, client, api_helpers, factories, enterprise_user
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
            scheduled_start=datetime.utcnow() + timedelta(minutes=20),
            member_schedule_id=member_schedule.id,
            member_schedule=member_schedule,
            product_id=product.id,
            product=product,
        )
        obfuscated_appt_id = obfuscate_appointment_id(appointment.id)

        res = client.post(
            f"/api/v2/appointments/{obfuscated_appt_id}/cancel",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({}),
        )

        assert res.status_code == 200
        res = client.post(
            f"/api/v2/appointments/{obfuscated_appt_id}/cancel",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({}),
        )

        assert res.status_code == 400

    def test_post_cancel_from_practitioner(
        self, client, api_helpers, factories, enterprise_user
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
            scheduled_start=datetime.utcnow() + timedelta(minutes=20),
            member_schedule_id=member_schedule.id,
            member_schedule=member_schedule,
            product_id=product.id,
            product=product,
        )
        obfuscated_appt_id = obfuscate_appointment_id(appointment.id)
        request = {"cancelled_note": "some notes"}

        res = client.post(
            f"/api/v2/appointments/{obfuscated_appt_id}/cancel",
            headers=api_helpers.json_headers(product.practitioner),
            data=api_helpers.json_data(request),
        )

        assert res.status_code == 200
        data = res.json
        assert data["id"] == obfuscated_appt_id
        assert data["state"] == "CANCELLED"
        assert data["product_id"] == product.id
        assert data["survey_types"] == [
            "cancellation_survey",
            "member_rating_v2",
            "member_rating_followup_v2",
        ]
        assert data["provider"]["id"] == product.user_id
        assert data["cancelled_at"] is not None
        db.session.expire_all()
        appointment = (
            db.session.query(Appointment).filter(Appointment.id == appointment.id).one()
        )
        assert appointment.cancelled_by_user_id == product.user_id
        assert appointment.json == {"cancelled_note": "some notes"}
