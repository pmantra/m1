import datetime
import json
from http import HTTPStatus
from unittest import mock

import pytest

from pytests.factories import AppointmentFactory


@pytest.fixture
def cancel_appointment_via_put(
    cancellation_data,
    put_appointment_on_endpoint,
):
    """Function to have a user attempt to cancel an appointment"""

    def cancel_appointment_via_put_func(appointment, canceller, note=None):
        full_data = cancellation_data
        if note:
            full_data["cancelled_note"] = note
        # PUT the cancellation data on an appointment to cancel it
        return put_appointment_on_endpoint(
            api_id=appointment.api_id,
            user=canceller,
            data_json_string=json.dumps(full_data),
        )

    return cancel_appointment_via_put_func


def test_prac_cancels_appointment(
    cancellable_appointment,
    cancel_appointment_via_put,
    assert_successful_http_appointment_cancellation,
    assert_cancellation_survey,
):
    """Tests the practitioner cancelling the appointment"""
    # Have the practitioner cancel the appointment
    res = cancel_appointment_via_put(
        appointment=cancellable_appointment,
        canceller=cancellable_appointment.practitioner,
    )

    # Assert the expected success
    assert_successful_http_appointment_cancellation(
        cancellation_result=res,
        appointment=cancellable_appointment,
        expected_user=cancellable_appointment.practitioner,
    )

    # Assert no cancellation survey is sent when a practitioner cancels the appointment
    assert_cancellation_survey(cancellation_response=res, has_cancellation_survey=False)


def test_member_cancels_appointment(
    cancellable_appointment,
    cancel_appointment_via_put,
    assert_successful_http_appointment_cancellation,
    assert_cancellation_survey,
):
    """Tests the member cancelling the appointment"""
    # Have the member cancel the appointment
    res = cancel_appointment_via_put(
        appointment=cancellable_appointment,
        canceller=cancellable_appointment.member,
    )

    # Assert the expected success
    assert_successful_http_appointment_cancellation(
        cancellation_result=res,
        appointment=cancellable_appointment,
        expected_user=cancellable_appointment.member,
    )

    # Assert cancellation survey is sent when a member cancels the appointment
    assert_cancellation_survey(cancellation_response=res, has_cancellation_survey=True)


def test_rando_cancels_appointment(
    factories,
    cancellable_appointment,
    cancel_appointment_via_put,
):
    """Tests an unassociated practitioner cancelling the appointment"""
    # Have a newly created practitioner cancel the appointment
    res = cancel_appointment_via_put(
        appointment=cancellable_appointment,
        canceller=factories.PractitionerUserFactory.create(),
    )

    # Assert that the action is forbidden
    assert res.status_code == HTTPStatus.FORBIDDEN


def test_appointment_cannot_change_cancelled_at(
    frozen_now,
    datetime_now,
    cancelled_appointment,
    cancel_appointment_via_put,
):
    res = cancel_appointment_via_put(
        appointment=cancelled_appointment, canceller=cancelled_appointment.member
    )
    assert res.status_code == 400


def test_appointment_cancel_member_note(
    cancellable_appointment,
    cancel_appointment_via_put,
    assert_successful_http_appointment_cancellation,
):
    """Tests the member cancelling the appointment with a note"""
    canceled_note_text = "reason"
    # Have the member cancel the appointment
    res = cancel_appointment_via_put(
        appointment=cancellable_appointment,
        canceller=cancellable_appointment.member,
        note=canceled_note_text,
    )

    # Assert the expected success
    assert_successful_http_appointment_cancellation(
        cancellation_result=res,
        appointment=cancellable_appointment,
        expected_user=cancellable_appointment.member,
        expected_note=canceled_note_text,
    )


def test_appointment_cancel_practitioner_note(
    cancellable_appointment,
    cancel_appointment_via_put,
    assert_successful_http_appointment_cancellation,
):
    """Tests the practitioner cancelling the appointment with a note"""
    canceled_note_text = "reason"
    # Have the member cancel the appointment
    res = cancel_appointment_via_put(
        appointment=cancellable_appointment,
        canceller=cancellable_appointment.practitioner,
        note=canceled_note_text,
    )

    # Assert the expected success
    assert_successful_http_appointment_cancellation(
        cancellation_result=res,
        appointment=cancellable_appointment,
        expected_user=cancellable_appointment.practitioner,
        expected_note=canceled_note_text,
    )


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_update_appointment_locale__user_edits_cancelled_appt(
    locale,
    release_mono_api_localization_on,
    client,
    cancelled_appointment,
    api_helpers,
):
    data = {}
    member = cancelled_appointment.member

    if locale is None:
        headers = api_helpers.json_headers(user=member)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=member), locale=locale
        )

    res = client.put(
        f"/api/v1/appointments/{cancelled_appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=headers,
    )

    assert res.json["message"] != "appointment_cancelled_edit_error_message"


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_update_appointment_locale__appointment_cannot_be_cancelled(
    locale,
    release_mono_api_localization_on,
    cancellable_appointment,
    api_helpers,
    client,
):
    data = {"cancelled_at": datetime.datetime.utcnow().isoformat()}
    member = cancellable_appointment.member

    if locale is None:
        headers = api_helpers.json_headers(user=member)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=member), locale=locale
        )

    appointment = AppointmentFactory.create()
    # have `appointment.cancel` return an appointment object without the cancelled_at attribute
    with mock.patch(
        "appointments.models.appointment.Appointment.cancel", return_value=appointment
    ):
        res = client.put(
            f"/api/v1/appointments/{cancellable_appointment.api_id}",
            data=api_helpers.json_data(data),
            headers=headers,
        )

    assert res.json["message"] != "appointment_cannot_cancel_error_message"
