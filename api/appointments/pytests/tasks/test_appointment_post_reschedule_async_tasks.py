import datetime

from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.tasks.appointments import appointment_post_reschedule_async_tasks
from pytests.factories import (
    AppointmentFactory,
    PractitionerAppointmentAckFactory,
    ProductFactory,
)


def test_appointment_post_reschedule_async_tasks_update_practitioner_apt_ack(
    datetime_now,
    db,
):
    """
    Test in the appointment_post_reschedule_async_tasks method, the PractitionerAppointmentAck
    row gets updated with the new timestamp and default boolean.
    """
    product = ProductFactory.create()
    original_scheduled_start = datetime_now - datetime.timedelta(hours=0.5)
    appointment = AppointmentFactory.create(
        created_at=datetime_now,
        product=product,
        scheduled_start=original_scheduled_start,
        member_started_at=None,
        practitioner_started_at=None,
        is_enterprise_factory=True,
        member_ended_at=None,
        practitioner_ended_at=None,
    )
    PractitionerAppointmentAckFactory.create(
        appointment=appointment,
        appointment_id=appointment.id,
        ack_by=datetime_now - datetime.timedelta(hours=2),
        warn_by=datetime_now - datetime.timedelta(hours=3),
        is_acked=True,
        is_alerted=True,
    )

    appointment_post_reschedule_async_tasks(appointment_id=appointment.id)

    practitioner_apt_ack = db.session.query(PractitionerAppointmentAck).filter(
        PractitionerAppointmentAck.appointment_id == appointment.id
    )[0]
    assert practitioner_apt_ack.ack_by == original_scheduled_start - datetime.timedelta(
        minutes=10
    )
    assert (
        practitioner_apt_ack.warn_by
        == original_scheduled_start - datetime.timedelta(minutes=90)
    )
    assert not practitioner_apt_ack.is_acked
    assert not practitioner_apt_ack.is_alerted
    assert not practitioner_apt_ack.is_warned
