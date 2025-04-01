import json
from unittest.mock import patch

import pytest

from appointments.services.v2.cancel_appointment_service import CancelAppointmentService
from appointments.utils.errors import (
    AppointmentNotFoundException,
    AppointmentNotInCancellableStateException,
)
from pytests import factories
from pytests.db_util import enable_db_performance_warnings
from storage.connection import db


class TestCancelAppointmentService:
    def test_cancel_appointment_appointment_not_found(self):
        member = factories.EnterpriseUserFactory.create()
        bad_appointment_id = 111111111

        with pytest.raises(AppointmentNotFoundException):
            CancelAppointmentService().cancel_appointment(member, bad_appointment_id)

    def test_member_cancel(
        self,
        enterprise_user,
        datetime_now,
    ):
        """Basic cancel case: verify that the appointment model has been updated after cancel."""
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

        with enable_db_performance_warnings(
            database=db,
            # warning_threshold=45,  # uncomment to view all queries being made
            failure_threshold=45,
        ):
            with patch(
                "appointments.services.v2.cancel_appointment_service.update_member_cancellations.delay"
            ) as mock_update_member_cancellations:
                CancelAppointmentService().cancel_appointment(
                    user=enterprise_user,
                    appointment_id=appointment.id,
                    cancelled_note=None,
                    admin_initiated=False,
                )

        cancelled_appointment = db.session.execute(
            "SELECT * FROM appointment"
        ).fetchone()
        assert cancelled_appointment.cancelled_at is not None
        assert cancelled_appointment.cancelled_by_user_id == appointment.member_id
        mock_update_member_cancellations.assert_called_once_with(
            appointment_id=appointment.id,
            admin_initiated=False,
            service_ns="appointments",
            team_ns="care_discovery",
        )

    def test_provider_cancel(
        self,
        enterprise_user,
        datetime_now,
    ):
        """Basic cancel case: verify that the appointment model has been updated after cancel."""
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

        with enable_db_performance_warnings(
            database=db,
            # warning_threshold=32,  # uncomment to view all queries being made
            failure_threshold=32,
        ):
            with patch(
                "appointments.services.v2.cancel_appointment_service.send_member_cancellation_note.delay"
            ) as mock_send_member_cancellation_note:
                CancelAppointmentService().cancel_appointment(
                    user=product.practitioner,
                    appointment_id=appointment.id,
                    cancelled_note="some notes",
                    admin_initiated=False,
                )

        cancelled_appointment = db.session.execute(
            "SELECT * FROM appointment"
        ).fetchone()
        assert cancelled_appointment.cancelled_at is not None
        assert cancelled_appointment.cancelled_by_user_id == product.user_id
        assert cancelled_appointment.json == json.dumps(
            {"cancelled_note": "some notes"}
        )
        mock_send_member_cancellation_note.assert_called_once_with(
            appointment_id=appointment.id,
            note="some notes",
            team_ns="virtual_care",
            service_ns="appointment_notifications",
        )

    def test_cancel_appointment__non_cancellable_state(
        self,
        enterprise_user,
        datetime_now,
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
        # This appointment should be in the state "payment_pending_or_resolved"
        # due to it having scheduled_start, started_at, and ended_at set
        appointment = factories.AppointmentFactory.create(
            scheduled_start=datetime_now,
            member_started_at=datetime_now,
            member_ended_at=datetime_now,
            practitioner_started_at=datetime_now,
            practitioner_ended_at=datetime_now,
            member_schedule_id=member_schedule.id,
            member_schedule=member_schedule,
            product_id=product.id,
            product=product,
        )

        with pytest.raises(AppointmentNotInCancellableStateException):
            CancelAppointmentService().cancel_appointment(
                enterprise_user, appointment.id
            )

    def test_cancel_appointment__cancellable_state(
        self,
        enterprise_user,
        datetime_now,
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

        with patch(
            "appointments.services.v2.cancel_appointment_service.update_member_cancellations.delay"
        ) as mock_update_member_cancellations:
            cancelled_appointment = CancelAppointmentService().cancel_appointment(
                enterprise_user, appointment.id
            )

        cancelled_appointment = db.session.execute(
            "SELECT * FROM appointment"
        ).fetchone()
        assert cancelled_appointment.cancelled_at is not None
        assert cancelled_appointment.cancelled_by_user_id == appointment.member_id
        mock_update_member_cancellations.assert_called_once_with(
            appointment_id=appointment.id,
            admin_initiated=False,
            service_ns="appointments",
            team_ns="care_discovery",
        )
