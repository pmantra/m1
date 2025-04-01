from http import HTTPStatus

from pytests.factories import RescheduleHistoryFactory
from views.schemas.common import MavenDateTime


def test_get_appointment_contains_rescheduled_from_previous_appointment_time(
    basic_appointment, get_appointment_from_endpoint_using_appointment
):
    appointment = basic_appointment
    reschedule_history = RescheduleHistoryFactory.create(
        appointment_id=basic_appointment.id
    )

    # Get the appointment from the endpoint
    response = get_appointment_from_endpoint_using_appointment(appointment)

    assert response.status_code == HTTPStatus.OK
    assert response.json.get(
        "rescheduled_from_previous_appointment_time"
    ) == MavenDateTime()._serialize(reschedule_history.scheduled_start, None, None)


def test_get_appointment_no_rescheduled_from_previous_appointment_time_member_user(
    enterprise_appointment, get_appointment_from_endpoint_using_appointment_user_member
):
    appointment = enterprise_appointment
    RescheduleHistoryFactory.create(appointment_id=enterprise_appointment.id)

    # Get the appointment from the endpoint
    response = get_appointment_from_endpoint_using_appointment_user_member(appointment)

    assert response.status_code == HTTPStatus.OK
    assert response.json.get("rescheduled_from_previous_appointment_time") is None
