from appointments.schemas.utils.reschedule_appointment import (
    get_rescheduled_from_previous_appointment_time,
)
from pytests.factories import RescheduleHistoryFactory
from views.schemas.common import MavenDateTime

# See other tests in api/appointments/pytests/resources/test_get_appointment_rescheduled_time.py


def get_rescheduled_from_previous_appointment_time_from_admin(basic_appointment):
    """
    Populate the rescheduled_from_previous_appointment_time field if the
    request comes from admin.
    """
    appointment = basic_appointment
    reschedule_history = RescheduleHistoryFactory.create(
        appointment_id=basic_appointment.id
    )
    context = {"admin": True}
    dd_metric_name = "dummy"

    response = get_rescheduled_from_previous_appointment_time(
        appointment, context, dd_metric_name
    )

    assert response == MavenDateTime()._serialize(
        reschedule_history.scheduled_start, None, None
    )
