import datetime
import json
import unittest
from http import HTTPStatus

import pytest

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.reschedule_history import RescheduleHistory


def test_patch_reschedule_happy_path(
    patch_reschedule_appointment_on_endpoint,
    setup_patch_reschedule_appointment_test,
    datetime_one_hour_later_iso_format,
    datetime_one_hour_later,
    datetime_now,
    db,
):
    """Test the happy path for the patch endpoint."""
    original_scheduled_start = datetime_now + datetime.timedelta(hours=0.5)
    reschedule_appointment_setup_values = setup_patch_reschedule_appointment_test(
        original_scheduled_start=original_scheduled_start,
        new_scheduled_start_time=datetime_one_hour_later_iso_format,
    )
    member = reschedule_appointment_setup_values.member
    product = reschedule_appointment_setup_values.product
    appointment = reschedule_appointment_setup_values.appointment
    reschedule_appointment_request = (
        reschedule_appointment_setup_values.reschedule_appointment_request
    )

    response = patch_reschedule_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=member,
        data_json_string=json.dumps(reschedule_appointment_request),
    )

    assert response.status_code == HTTPStatus.OK
    response_json = json.loads(response.data)
    # assert the appointment's scheduled start and end time is updated
    assert response_json["scheduled_start"] == datetime_one_hour_later_iso_format
    assert (
        response_json["scheduled_end"]
        == (
            datetime_one_hour_later + datetime.timedelta(minutes=product.minutes)
        ).isoformat()
    )

    # assert a reschedule history row is created with the original schedule start and end time
    reschedule_history = db.session.query(RescheduleHistory).filter(
        RescheduleHistory.appointment_id == appointment.id
    )[0]
    assert reschedule_history.scheduled_start == original_scheduled_start
    assert (
        reschedule_history.scheduled_end
        == original_scheduled_start + datetime.timedelta(minutes=product.minutes)
    )


def test_patch_reschedule_reschedule_after_the_start_time(
    patch_reschedule_appointment_on_endpoint,
    setup_patch_reschedule_appointment_test,
    datetime_one_hour_later_iso_format,
    datetime_now,
):
    """
    Test when user wants to reschedule after the appointment's start time
    is passed. It will return a 400 HTTP status with an error message.
    """
    original_scheduled_start = datetime_now - datetime.timedelta(hours=0.5)
    reschedule_appointment_setup_values = setup_patch_reschedule_appointment_test(
        original_scheduled_start=original_scheduled_start,
        new_scheduled_start_time=datetime_one_hour_later_iso_format,
    )
    member = reschedule_appointment_setup_values.member
    appointment = reschedule_appointment_setup_values.appointment
    reschedule_appointment_request = (
        reschedule_appointment_setup_values.reschedule_appointment_request
    )

    response = patch_reschedule_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=member,
        data_json_string=json.dumps(reschedule_appointment_request),
    )

    # import pdb; pdb.set_trace();
    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_json = json.loads(response.data)
    assert (
        response_json["message"]
        == "Can't reschedule after the appointment's start time."
    )


@pytest.mark.parametrize(
    "appointment_state",
    [
        APPOINTMENT_STATES.overdue,
        APPOINTMENT_STATES.cancelled,
        APPOINTMENT_STATES.disputed,
    ],
)
@unittest.mock.patch(
    "appointments.resources.reschedule_appointment.feature_flags.bool_variation"
)
def test_patch_reschedule__appointment_state_not_scheduled(
    mock_feature_flag,
    patch_reschedule_appointment_on_endpoint,
    setup_patch_reschedule_appointment_test,
    datetime_one_hour_later_iso_format,
    datetime_now,
    appointment_state,
):
    """
    Test when user wants to reschedule an appointment that is not in the SCHEDULED
    state, we return a 400.
    """
    # Given an appointment with a state that is not SCHEDULED
    mock_feature_flag.return_value = True
    original_scheduled_start = datetime_now - datetime.timedelta(hours=0.5)
    reschedule_appointment_setup_values = setup_patch_reschedule_appointment_test(
        original_scheduled_start=original_scheduled_start,
        new_scheduled_start_time=datetime_one_hour_later_iso_format,
    )
    member = reschedule_appointment_setup_values.member
    appointment = reschedule_appointment_setup_values.appointment

    if appointment_state == APPOINTMENT_STATES.cancelled:
        appointment.cancelled_at = datetime_now - datetime.timedelta(minutes=1)
    elif appointment_state == APPOINTMENT_STATES.disputed:
        appointment.disputed_at = datetime_now - datetime.timedelta(minutes=1)
    # appointment_state == APPOINTMNET_STATES.overdue is set up as the default

    reschedule_appointment_request = (
        reschedule_appointment_setup_values.reschedule_appointment_request
    )

    # When we hit the patch /reschedule endpoint
    response = patch_reschedule_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=member,
        data_json_string=json.dumps(reschedule_appointment_request),
    )

    # Then we throw a 400 with the correct error message
    assert response.status_code == HTTPStatus.BAD_REQUEST
    response_json = json.loads(response.data)
    assert (
        response_json["message"]
        == "Can't reschedule an appointment that is not in the SCHEDULED state."
    )


@unittest.mock.patch(
    "appointments.resources.reschedule_appointment.feature_flags.bool_variation"
)
def test_patch_reschedule__marketplace_reschedule_within_2_hours(
    mock_feature_flag,
    patch_reschedule_appointment_on_endpoint,
    setup_patch_reschedule_appointment_test,
    datetime_one_hour_later_iso_format,
    datetime_now,
):
    """
    Test when a marketplace user wants to reschedule within 2 hours of the
    appointment's start time. It will return a 403 HTTP status with an error message.
    """
    # Given a marketplace member with an appointment in the next 2 hrs
    mock_feature_flag.return_value = True
    original_scheduled_start = datetime_now + datetime.timedelta(hours=0.5)
    reschedule_appointment_setup_values = setup_patch_reschedule_appointment_test(
        original_scheduled_start=original_scheduled_start,
        new_scheduled_start_time=datetime_one_hour_later_iso_format,
        is_enterprise=False,
    )
    member = reschedule_appointment_setup_values.member
    appointment = reschedule_appointment_setup_values.appointment
    reschedule_appointment_request = (
        reschedule_appointment_setup_values.reschedule_appointment_request
    )

    # When we hit the patch /reschedule endpoint
    response = patch_reschedule_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=member,
        data_json_string=json.dumps(reschedule_appointment_request),
    )

    # Then our response is 403 FORBIDDEN and the message is as expected
    assert response.status_code == HTTPStatus.FORBIDDEN
    response_json = json.loads(response.data)
    assert (
        response_json["message"]
        == "Marketplace members can't reschedule an appointment within 2 hours of scheduled start."
    )


@unittest.mock.patch(
    "appointments.resources.reschedule_appointment.feature_flags.bool_variation"
)
def test_patch_reschedule__marketplace_reschedule_before_2_hours(
    mock_feature_flag,
    patch_reschedule_appointment_on_endpoint,
    setup_patch_reschedule_appointment_test,
    datetime_one_hour_later,
    datetime_one_hour_later_iso_format,
    datetime_now,
    db,
):
    """
    Test when a marketplace user wants to reschedule more than 2 hours before the
    appointment's start time. It will be successful.
    """
    # Given a marketplace member with an appointment more than 2 hrs from now
    mock_feature_flag.return_value = True
    original_scheduled_start = datetime_now + datetime.timedelta(hours=3)
    reschedule_appointment_setup_values = setup_patch_reschedule_appointment_test(
        original_scheduled_start=original_scheduled_start,
        new_scheduled_start_time=datetime_one_hour_later_iso_format,
        is_enterprise=False,
    )
    member = reschedule_appointment_setup_values.member
    product = reschedule_appointment_setup_values.product
    appointment = reschedule_appointment_setup_values.appointment
    reschedule_appointment_request = (
        reschedule_appointment_setup_values.reschedule_appointment_request
    )

    # When we hit the patch /reschedule endpoint
    response = patch_reschedule_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=member,
        data_json_string=json.dumps(reschedule_appointment_request),
    )

    # Then our response is 200 OK and the appointment is rescheduled
    assert response.status_code == HTTPStatus.OK
    response_json = json.loads(response.data)
    # the appointment's scheduled start and end time is updated
    assert response_json["scheduled_start"] == datetime_one_hour_later_iso_format
    assert (
        response_json["scheduled_end"]
        == (
            datetime_one_hour_later + datetime.timedelta(minutes=product.minutes)
        ).isoformat()
    )

    # a reschedule history row is created with the original schedule start and end time
    reschedule_history = db.session.query(RescheduleHistory).filter(
        RescheduleHistory.appointment_id == appointment.id
    )[0]
    assert reschedule_history.scheduled_start == original_scheduled_start
    assert (
        reschedule_history.scheduled_end
        == original_scheduled_start + datetime.timedelta(minutes=product.minutes)
    )


@unittest.mock.patch(
    "appointments.resources.reschedule_appointment.feature_flags.bool_variation"
)
def test_patch_reschedule__schedule_event_id_updated(
    mock_feature_flag,
    patch_reschedule_appointment_on_endpoint,
    setup_patch_reschedule_appointment_test,
    datetime_one_hour_later_iso_format,
    datetime_one_hour_later,
    datetime_now,
    db,
):
    """Test the happy path for the patch endpoint, and confirm with the feature flag on
    we update schedule_event_id when the appointment is rescheduled."""
    # Given
    mock_feature_flag.return_value = True
    original_scheduled_start = datetime_now + datetime.timedelta(hours=3)
    reschedule_appointment_setup_values = setup_patch_reschedule_appointment_test(
        original_scheduled_start=original_scheduled_start,
        new_scheduled_start_time=datetime_one_hour_later_iso_format,
    )
    member = reschedule_appointment_setup_values.member
    product = reschedule_appointment_setup_values.product
    appointment = reschedule_appointment_setup_values.appointment
    reschedule_appointment_request = (
        reschedule_appointment_setup_values.reschedule_appointment_request
    )
    original_schedule_event_id = appointment.schedule_event_id

    # When
    response = patch_reschedule_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=member,
        data_json_string=json.dumps(reschedule_appointment_request),
    )

    # Then
    assert response.status_code == HTTPStatus.OK
    response_json = json.loads(response.data)
    # assert the appointment's scheduled start and end time is updated
    assert response_json["scheduled_start"] == datetime_one_hour_later_iso_format
    assert (
        response_json["scheduled_end"]
        == (
            datetime_one_hour_later + datetime.timedelta(minutes=product.minutes)
        ).isoformat()
    )

    # assert a reschedule history row is created with the original schedule start and end time
    reschedule_history = db.session.query(RescheduleHistory).filter(
        RescheduleHistory.appointment_id == appointment.id
    )[0]
    rescheduled_appointment = Appointment.query.get(appointment.id)
    assert reschedule_history.scheduled_start == original_scheduled_start
    assert (
        reschedule_history.scheduled_end
        == original_scheduled_start + datetime.timedelta(minutes=product.minutes)
    )
    # assert the schedule_event_id is updated
    assert rescheduled_appointment.schedule_event_id
    assert original_schedule_event_id != rescheduled_appointment.schedule_event_id
