import datetime

import pytest

from appointments.models.appointment import Appointment
from appointments.services.schedule import (
    BookingConflictException,
    managed_appointment_booking_availability,
)
from storage.connection import db


def test_managed_appointment_booking_availability(
    factories, practitioner_user, member_with_add_appointment
):
    now = datetime.datetime.utcnow()
    practitioner = practitioner_user()
    scheduled_start = now + datetime.timedelta(minutes=20)  # default booking buffer

    schedule_event = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=scheduled_start,
        ends_at=now + datetime.timedelta(minutes=500),
    )
    product = practitioner.products[0]

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    with managed_appointment_booking_availability(product, scheduled_start, member):
        appointment = Appointment(
            schedule_event=schedule_event,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_start,
            product=product,
            purpose="",
            member_schedule=member.schedule,
            cancellation_policy=factories.CancellationPolicyFactory.create(),
            client_notes="",
            privacy="basic",
            privilege_type="basic",
        )
        db.session.add(appointment)
        db.session.commit()

    with pytest.raises(BookingConflictException):
        with managed_appointment_booking_availability(product, scheduled_start, member):
            appointment = Appointment(
                schedule_event=schedule_event,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_start,
                product=product,
                purpose="",
                member_schedule=member.schedule,
                cancellation_policy=factories.CancellationPolicyFactory.create(),
                client_notes="",
                privacy="basic",
                privilege_type="basic",
            )
            db.session.add(appointment)
            db.session.commit()
