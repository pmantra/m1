import datetime
import json
from http import HTTPStatus
from time import sleep
from unittest import mock
from unittest.mock import patch

import pytest
from flask_restful import abort
from maven import feature_flags

from appointments.models.appointment import Appointment, PostSessionNoteUpdate
from appointments.models.constants import PRIVACY_CHOICES
from appointments.models.payments import FeeAccountingEntry
from dosespot.resources.dosespot_api import DoseSpotAPI
from models.questionnaires import QuestionTypes
from pytests.db_util import enable_db_performance_warnings
from storage.connection import db
from utils.flag_groups import APPOINTMENT_ALLOW_RX_OVERWRITE


@pytest.fixture
def ff_test_data():
    with feature_flags.test_data() as td:
        yield td


@pytest.fixture
def practitioner_enabled_for_prescribing(factories):
    return factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[factories.VerticalFactory.create()],
        practitioner_profile__dosespot={
            "clinic_key": "foo",
            "clinic_id": "bar",
            "user_id": "foobar",
        },
    )


@pytest.fixture
def appointment_with_practitioner_enabled_for_prescribing(
    factories,
    practitioner_enabled_for_prescribing,
):
    def make_appointment(privacy=None, member_schedule=None):
        appointment = factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioner_enabled_for_prescribing,
            privacy=privacy,
            member_schedule=member_schedule,
        )
        return appointment

    return make_appointment


@pytest.fixture
def member_enabled_for_prescription(factories):
    member = factories.MemberFactory.create(
        member_profile__first_name="A_test1",
        member_profile__last_name="member1",
        member_profile__phone_number="2125551010",
    )
    factories.AddressFactory.create(user=member)
    factories.ScheduleFactory.create(user=member)
    factories.HealthProfileFactory.create(user=member, has_birthday=True)
    return member


def test_simple_put(
    cancellable_appointment,
    simple_post_session_data,
    put_appointment_on_endpoint,
    assert_successful_http_update,
):
    """Tests a basic PUT on an appointment. This is the base case and should
    succeed with no complications.
    """
    # PUT post session data on the appointment
    res = put_appointment_on_endpoint(
        api_id=cancellable_appointment.api_id,
        user=cancellable_appointment.practitioner,
        data_json_string=json.dumps(simple_post_session_data),
    )

    # Assert that the PUT succeeded as expected
    assert_successful_http_update(
        update_result=res,
        expected_data=simple_post_session_data,
    )


def test_put__base_db_calls(
    cancellable_appointment,
    simple_post_session_data,
    put_appointment_on_endpoint,
    assert_successful_http_update,
):
    """ """
    with enable_db_performance_warnings(
        database=db,
        failure_threshold=57,
    ):
        # PUT post session data on the appointment
        res = put_appointment_on_endpoint(
            api_id=cancellable_appointment.api_id,
            user=cancellable_appointment.practitioner,
            data_json_string=json.dumps(simple_post_session_data),
        )

    assert res.status_code == 200


@pytest.mark.parametrize(
    argnames="ld_mock_value, mock_called_assertion",
    argvalues=(
        (("release-mpractice-deprecate-appointment-save-notes", True), False),
        (("release-mpractice-deprecate-appointment-save-notes", False), True),
    ),
    ids=[
        "refactor save enabled",
        "refactor save disabled",
    ],
)
def test_put_with_notes_flags(
    add_appointment_post_session_note,
    cancellable_appointment,
    simple_post_session_data,
    put_appointment_on_endpoint,
    ld_mock_value,
    mock_called_assertion,
    ff_test_data,
):
    """
    Tests that the endpoint does not call certain note updating logic when flag is enabled
    """
    post_session = add_appointment_post_session_note(
        appointment=cancellable_appointment,
        content="Do the thing.",
        created_at=datetime.datetime.utcnow(),
    )
    # PUT post session data on the appointment
    with mock.patch(
        "appointments.resources.appointment.AppointmentResource._update_internal_note"
    ) as mock_internal_note, mock.patch(
        "appointments.resources.appointment.Appointment.update_post_session",
        return_value=PostSessionNoteUpdate(
            post_session=post_session, should_send=False
        ),
    ) as mock_post_session_note:
        ff_test_data.update(
            ff_test_data.flag(ld_mock_value[0]).variation_for_all(ld_mock_value[1])
        )

        res = put_appointment_on_endpoint(
            api_id=cancellable_appointment.api_id,
            user=cancellable_appointment.practitioner,
            data_json_string=json.dumps(simple_post_session_data),
        )

        # Assert that the PUT succeeded and the mocks were called depending on flag
        assert res.status_code == HTTPStatus.OK
        assert mock_post_session_note.called == mock_called_assertion
        assert mock_internal_note.called == mock_called_assertion


def test_put_member_set_start_time2(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that the member can set the member started at but not the practitioner's started at.
    """
    appointment = scheduled_appointment
    started_at = (
        (appointment.scheduled_start + datetime.timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )

    data = {
        "practitioner_started_at": started_at,
        "member_started_at": started_at,
    }

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    res_data = api_helpers.load_json(res)

    assert res.status_code == 200
    assert res_data["member_started_at"]
    assert not res_data["practitioner_started_at"]


def test_put_practitioner_set_start_time3(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that the practitioner can set the practitioner started at but not the member's started at.
    """
    appointment = scheduled_appointment
    started_at = (
        (appointment.scheduled_start + datetime.timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )

    data = {
        "practitioner_started_at": started_at,
        "member_started_at": started_at,
    }

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.practitioner),
    )
    res_data = api_helpers.load_json(res)

    assert res.status_code == 200
    assert res_data["practitioner_started_at"]
    assert not res_data["member_started_at"]


def test_put_member_set_start_time(
    cancellable_appointment,
    put_appointment_on_endpoint,
    api_helpers,
):
    """
    Tests that the member can set their start time but not the provider's start time
    """
    product = cancellable_appointment.practitioner.products[0]

    data = {
        "product_id": product.id,
        "scheduled_start": cancellable_appointment.scheduled_start.isoformat(),
    }
    res = put_appointment_on_endpoint(
        api_id=cancellable_appointment.api_id,
        user=cancellable_appointment.practitioner,
        data_json_string=json.dumps(data),
    )

    appointment_json = api_helpers.load_json(res)
    start_datetime = datetime.datetime.utcnow()

    data = {
        "practitioner_started_at": start_datetime.isoformat(),
        "member_started_at": start_datetime.isoformat(),
    }

    res = put_appointment_on_endpoint(
        api_id=appointment_json["id"],
        user=cancellable_appointment.member,
        data_json_string=json.dumps(data),
    )
    res_data = api_helpers.load_json(res)
    assert res_data["practitioner_started_at"] is None
    assert res_data["member_started_at"] is not None


def test_put_provider_set_start_time(
    cancellable_appointment, put_appointment_on_endpoint, api_helpers
):
    """
    Tests that the provider can set their start time but not the member's
    """
    product = cancellable_appointment.practitioner.products[0]
    data = {
        "product_id": product.id,
        "scheduled_start": cancellable_appointment.scheduled_start.isoformat(),
    }
    res = put_appointment_on_endpoint(
        api_id=cancellable_appointment.api_id,
        user=cancellable_appointment.practitioner,
        data_json_string=json.dumps(data),
    )

    appointment_json = api_helpers.load_json(res)
    start_datetime = datetime.datetime.utcnow()

    data = {
        "practitioner_started_at": start_datetime.isoformat(),
        "member_started_at": start_datetime.isoformat(),
    }

    res = put_appointment_on_endpoint(
        api_id=appointment_json["id"],
        user=cancellable_appointment.practitioner,
        data_json_string=json.dumps(data),
    )
    res_data = api_helpers.load_json(res)
    assert res_data["practitioner_started_at"] is not None
    assert res_data["member_started_at"] is None


def test_appointment_not_found(
    put_appointment_on_endpoint, simple_post_session_data, factories
):
    """Tests that attempting to PUT on a non-existent appointment will
    return an HTTPStatus.NOT_FOUND (404)
    """
    res = put_appointment_on_endpoint(
        api_id=19999999,
        user=factories.DefaultUserFactory.create(),
        data_json_string=json.dumps(simple_post_session_data),
    )

    # Assert the error
    assert res.status_code == HTTPStatus.NOT_FOUND


def test_forbidden_appointment_practitioner(
    basic_appointment,
    put_appointment_on_endpoint,
    simple_post_session_data,
    factories,
):
    """Tests the case where one practitioner tries to edit the appointment
    of another practitioner's. This should return HTTPStatus.FORBIDDEN (403)
    """
    res = put_appointment_on_endpoint(
        api_id=basic_appointment.api_id,
        user=factories.PractitionerUserFactory.create(),
        data_json_string=json.dumps(simple_post_session_data),
    )

    # Assert the error
    assert res.status_code == HTTPStatus.FORBIDDEN


def test_put_on_cancelled_appointment_bad_request(
    cancellable_appointment,
    put_appointment_on_endpoint_using_appointment,
    simple_post_session_data,
):
    """Tests that a PUT on a cancelled appointment will return
    HTTPStatus.BAD_REQUEST (400)
    """
    cancellable_appointment.cancelled_at = datetime.datetime.now()
    res = put_appointment_on_endpoint_using_appointment(
        appointment=cancellable_appointment,
        data_json_string=json.dumps(simple_post_session_data),
        appointment_user=cancellable_appointment.practitioner,
    )

    assert res.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.usefixtures("frozen_now")
def test_member_completes_appt_with_no_previous_started_at_value(
    basic_appointment,
    put_appointment_on_endpoint_using_appointment,
    datetime_one_hour_earlier_iso_format,
    datetime_one_hour_earlier,
    datetime_one_hour_later_iso_format,
    datetime_one_hour_later,
):
    """Tests the member marking the appointment as completed by
    setting the member_ended_at value (member_started_at value will be
    passed in through PUT in this test case). The orginal appointment doesn't
    have the member_started_at and member_ended_at value. The PUT method will
    update both values in the appointment.
    """
    # PUT time information on the appointment.
    res = put_appointment_on_endpoint_using_appointment(
        appointment=basic_appointment,
        data_json_string=json.dumps(
            {
                "id": basic_appointment.api_id,
                "member_started_at": datetime_one_hour_earlier_iso_format,
                "member_ended_at": datetime_one_hour_later_iso_format,
            }
        ),
        appointment_user=basic_appointment.member,
    )

    # Assert that the endpoint returns successfully
    assert res.status_code == HTTPStatus.OK

    # Remove the appointment from the db cache to prevent lazy loading.
    db.session.expire(basic_appointment)

    # Get a fresh copy of the appointment
    appt = Appointment.query.get(basic_appointment.id)
    # The member_started_at and member_ended_at values are overriden by
    # the PUT method.
    assert appt.member_started_at == datetime_one_hour_earlier
    assert appt.member_ended_at == datetime_one_hour_later


@pytest.mark.usefixtures("frozen_now")
def test_prac_completes_appt_with_no_previous_started_at_value(
    basic_appointment,
    put_appointment_on_endpoint_using_appointment,
    datetime_one_hour_earlier_iso_format,
    datetime_one_hour_earlier,
    datetime_one_hour_later_iso_format,
    datetime_one_hour_later,
):
    """Tests the practitioner marking the appointment as completed by
    setting the practitioner_ended_at value (practitioner_started_at
    and member_ended_at value will be passed in through PUT in this
    test case). The orginal appointment doesn't have the practitioner_started_at,
    practitioner_ended_at and member_ended_at value. The PUT method will
    update all the values in the appointment.
    """
    # PUT time information on the appointment.
    res = put_appointment_on_endpoint_using_appointment(
        appointment=basic_appointment,
        data_json_string=json.dumps(
            {
                "id": basic_appointment.api_id,
                "practitioner_started_at": datetime_one_hour_earlier_iso_format,
                "practitioner_ended_at": datetime_one_hour_later_iso_format,
                "member_ended_at": datetime_one_hour_later_iso_format,
            }
        ),
        appointment_user=basic_appointment.practitioner,
    )

    # Assert that the endpoint returns successfully
    assert res.status_code == HTTPStatus.OK

    # Remove the appointment from the db cache to prevent lazy loading.
    db.session.expire(basic_appointment)

    # Get a fresh copy of the appointment
    appt = Appointment.query.get(basic_appointment.id)
    # The practitioner_started_at, practitioner_ended_at and member_ended_at values are overriden by
    # the PUT method.
    assert appt.practitioner_started_at == datetime_one_hour_earlier
    assert appt.practitioner_ended_at == datetime_one_hour_later
    assert appt.member_ended_at == datetime_one_hour_later


@pytest.mark.usefixtures("frozen_now")
def test_prac_completes_appt(
    basic_appointment,
    put_appointment_on_endpoint_using_appointment,
    datetime_one_hour_earlier_iso_format,
    datetime_now,
    datetime_one_hour_earlier,
    datetime_one_hour_later_iso_format,
):
    """Tests the practitioner marking the appointment as completed by
    setting the practitioner_ended_at value. Technically, also started
    the appointment since the practitioner_started_at value is being set.
    """
    # PUT time information on the appointment. Note that the time information
    # will be ignored and set to the "current" time by the server, which
    # has been frozen at datetime_now by the frozen_now fixture.
    res = put_appointment_on_endpoint_using_appointment(
        appointment=basic_appointment,
        data_json_string=json.dumps(
            {
                "id": basic_appointment.api_id,
                "phone_call_at": datetime_one_hour_later_iso_format,
                "practitioner_started_at": datetime_one_hour_earlier_iso_format,
                "practitioner_ended_at": datetime_one_hour_later_iso_format,
                "member_ended_at": datetime_one_hour_later_iso_format,
            }
        ),
        appointment_user=basic_appointment.practitioner,
    )

    # Assert that the endpoint returns successfully
    assert res.status_code == HTTPStatus.OK

    # Remove the appointment from the db cache to prevent lazy loading.
    db.session.expire(basic_appointment)

    # Get a fresh copy of the appointment
    appt = Appointment.query.get(basic_appointment.id)
    # The practitioner_started_at is overriden by the PUT method.
    assert appt.practitioner_started_at == datetime_one_hour_earlier
    # Assert that the time information saved is datetime_now, which
    # is the time set in the frozen_now fixture
    assert appt.phone_call_at == datetime_now
    assert appt.practitioner_ended_at == datetime_now
    assert appt.member_ended_at == datetime_now


@pytest.mark.usefixtures("frozen_now")
def test_prac_starts_appt_even_if_dosespot_fails(
    basic_appointment,
    enable_appointment_rx,
    put_appointment_on_endpoint_using_appointment,
    datetime_one_hour_earlier_iso_format,
    datetime_one_hour_earlier,
):
    """Tests the practitioner starting the appointment even if dosespot
    (pharmacy info) fails. The expected behavior is that an
    HTTPStatus.BAD_REQUEST is returned, but the appointment is still
    marked as started.
    """
    with patch(
        "appointments.resources.appointment.AppointmentResource._check_and_set_pharmacy"
    ) as mock_check_and_set_pharmacy:
        # Enable RX on the appointment
        enable_appointment_rx(basic_appointment)

        # Setup patch to return BAD_REQUEST when checking pharmacy info
        def abort_request(*args, **kwargs):
            abort(HTTPStatus.BAD_REQUEST, message="pharmacy error")

        mock_check_and_set_pharmacy.side_effect = abort_request

        # Start the appointment by PATCHing the start time and include
        # prescription into to trigger pharmacy check
        res = put_appointment_on_endpoint_using_appointment(
            appointment=basic_appointment,
            data_json_string=json.dumps(
                {
                    "id": basic_appointment.api_id,
                    "practitioner_started_at": datetime_one_hour_earlier_iso_format,
                    "prescription_info": {"pharmacy_id": "F00B4R"},
                }
            ),
            appointment_user=basic_appointment.practitioner,
        )

        # Assert the BAD_REQUEST from the dosespot failure
        assert res.status_code == HTTPStatus.BAD_REQUEST

        # Remove the appointment from the db cache to prevent lazy loading.
        db.session.expire(basic_appointment)

        # Get a fresh copy of the appointment
        appt = Appointment.query.get(basic_appointment.id)
        # Assert that the start time is datetime_one_hour_earlier, which
        # is updated by PUT
        assert appt.practitioner_started_at == datetime_one_hour_earlier


@pytest.mark.usefixtures("frozen_now")
def test_partial_put_does_not_overwrite(
    cancellable_appointment, datetime_now, put_appointment_on_endpoint, api_helpers
):
    appointment = cancellable_appointment
    p60 = datetime_now + datetime.timedelta(minutes=60)
    data = {
        "member_started_at": datetime_now.isoformat(),
        "member_ended_at": p60.isoformat(),
    }

    res = put_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=appointment.member,
        data_json_string=json.dumps(data),
    )
    assert res.status_code == 200

    assert FeeAccountingEntry.query.count() == 0

    second_start = (datetime_now + datetime.timedelta(minutes=20)).isoformat()
    data = {"member_started_at": second_start}

    res = put_appointment_on_endpoint(
        api_id=appointment.api_id,
        user=appointment.member,
        data_json_string=json.dumps(data),
    )

    data = api_helpers.load_json(res)
    assert data["member_started_at"] != second_start


def test_appointment_member_can_save_note(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that member can add a pre-appointment note
    """
    appointment = scheduled_appointment
    member = appointment.member
    res = client.get(
        f"/api/v1/appointments/{appointment.api_id}",
        headers=api_helpers.json_headers(member),
    )
    data = api_helpers.load_json(res)
    expected_note = "Testing the member pre-appointment note..."

    data["pre_session"]["notes"] = expected_note

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member),
    )
    data = api_helpers.load_json(res)

    assert data["pre_session"]["notes"] == expected_note


def test_appointment_member_can_edit_note(
    client,
    api_helpers,
    scheduled_appointment_with_member_note,
):
    """
    Tests that member can edit an existing pre-appointment note
    """
    appointment = scheduled_appointment_with_member_note
    expected_note = "New pre-session note"
    data = {"pre_session": {"notes": expected_note}}
    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    data = api_helpers.load_json(res)

    assert data["pre_session"]["notes"] == expected_note


def test_add_pharmacy_to_appointment(
    client,
    api_helpers,
    member_enabled_for_prescription,
    appointment_with_practitioner_enabled_for_prescribing,
):
    with patch.object(
        DoseSpotAPI,
        "validate_pharmacy",
        return_value=({"PharmacyId": 1}),
    ):
        data = {"prescription_info": {"pharmacy_id": 1}}
        appointment = appointment_with_practitioner_enabled_for_prescribing(
            member_schedule=member_enabled_for_prescription.schedule
        )
        res = client.put(
            f"/api/v1/appointments/{appointment.api_id}",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(appointment.member),
        )

        assert res.status_code == 200
        data = api_helpers.load_json(res)
        assert data["prescription_info"]["pharmacy_id"] == "1"


def test_cannot_add_pharmacy_info_to_anon_appointment(
    client, api_helpers, appointment_with_practitioner_enabled_for_prescribing
):
    """
    Test that a provider who can prescribe can't add pharmacy info to
    an anonymous appointment
    requires appointment be with a provider who has dosespot information set
    """
    data = {"prescription_info": {"pharmacy_id": 100}}
    appointment = appointment_with_practitioner_enabled_for_prescribing(
        privacy=PRIVACY_CHOICES.anonymous
    )

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )

    assert res.status_code == 400


def test_set_pharma_id_bad(
    client,
    api_helpers,
    appointment_with_practitioner_enabled_for_prescribing,
    member_enabled_for_prescription,
):
    with patch.object(
        DoseSpotAPI,
        "validate_pharmacy",
        return_value=({}),
    ):
        data = {"prescription_info": {"pharmacy_id": 100}}
        appointment = appointment_with_practitioner_enabled_for_prescribing(
            member_schedule=member_enabled_for_prescription.schedule
        )
        res = client.put(
            f"/api/v1/appointments/{appointment.api_id}",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(appointment.member),
        )
        assert res.status_code == 200


def test_set_pharma_id_not_enabled(
    client,
    api_helpers,
    valid_appointment_with_user,
    appointment_with_practitioner_enabled_for_prescribing,
):
    """
    Check that pharmacy info can't be added for a member who
    isn't enabled for prescriptions
    """
    data = {"prescription_info": {"pharmacy_id": 100}}
    appointment = appointment_with_practitioner_enabled_for_prescribing()
    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    assert res.status_code == 400


def test_appointment_add_ratings(client, api_helpers, ended_appointment):
    data = {"ratings": {"cat1": 5}}

    res = client.put(
        f"/api/v1/appointments/{ended_appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(ended_appointment.member),
    )
    data = api_helpers.load_json(res)

    assert data["ratings"] == {"cat1": 5}


def test_disconnected_data_with_invalid_type_returns_400(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that disconnected data with invalid type (e.g. not a date or datetime) returns http status code 400.
    """
    appointment = scheduled_appointment
    disconnected_at = "test"
    data = {"member_disconnected_at": disconnected_at}

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )

    assert not appointment.member_started_at
    assert not appointment.json.get("member_disconnect_times")
    assert res.status_code == 400


def test_appointment_can_process_member_disconnected_data(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that member disconnected data can be successfully processed.
    """
    appointment = scheduled_appointment
    disconnected_at = (
        (appointment.scheduled_start + datetime.timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )
    data = {"member_disconnected_at": disconnected_at}

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    data = api_helpers.load_json(res)

    assert res.status_code == 200
    assert data["member_started_at"] == disconnected_at
    assert appointment.json.get("member_disconnect_times") == [disconnected_at]


def test_appointment_can_process_practitioner_disconnected_data(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that practitioner disconnected data can be successfully processed.
    """
    appointment = scheduled_appointment
    disconnected_at = (
        (appointment.scheduled_start + datetime.timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )
    data = {"practitioner_disconnected_at": disconnected_at}

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.practitioner),
    )
    data = api_helpers.load_json(res)

    assert res.status_code == 200
    assert data["practitioner_started_at"] == disconnected_at
    assert appointment.json.get("practitioner_disconnect_times") == [disconnected_at]


def test_appointment_can_process_member_disconnected_data_and_member_survey_results(
    client,
    api_helpers,
    scheduled_appointment,
    valid_questionnaire_with_oid,
):
    """
    Tests that member disconnected data and member survey results can be successfully processed.
    """
    with patch(
        "appointments.resources.appointment.AppointmentResource._process_member_rating_disconnections"
    ) as mock_process_member_rating:
        questionnaire = valid_questionnaire_with_oid(oid="reconnection_test")
        questions = questionnaire.question_sets[0].questions
        question = next(q for q in questions if q.type == QuestionTypes.TEXT)

        appointment = scheduled_appointment
        disconnected_at = (
            (appointment.scheduled_start + datetime.timedelta(minutes=1))
            .replace(microsecond=0)
            .isoformat()
        )

        recorded_answers = [
            {
                "question_id": question.id,
                "user_id": appointment.member.id,
                "answer_id": None,
                "appointment_id": appointment.api_id,
                "text": "sample text",
            },
        ]

        data = {
            "member_disconnected_at": disconnected_at,
            "member_rating": {"recorded_answers": recorded_answers},
        }

        res = client.put(
            f"/api/v1/appointments/{appointment.api_id}",
            data=json.dumps(data),
            headers=api_helpers.json_headers(appointment.member),
        )

        res_data = json.loads(res.data)

        assert res.status_code == 200
        assert mock_process_member_rating.called
        assert res_data["member_rating"]
        assert res_data["member_started_at"] == disconnected_at
        assert appointment.json.get("member_disconnect_times") == [disconnected_at]


def test_appointment_can_process_member_disconnected_data_and_will_not_change_practitioner_properties(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that member disconnected data can be successfully processed and it will not change
    practitioner properties.
    """
    appointment = scheduled_appointment
    disconnected_at = (
        (appointment.scheduled_start + datetime.timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )
    data = {"member_disconnected_at": disconnected_at}

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    data = api_helpers.load_json(res)

    assert res.status_code == 200
    assert data["member_started_at"] == disconnected_at
    assert appointment.json.get("member_disconnect_times") == [disconnected_at]
    assert not data["practitioner_started_at"]
    assert not appointment.json.get("practitioner_disconnect_times")


def test_appointment_can_process_practitioner_disconnected_data_and_will_not_change_member_properties(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that practitioner disconnected data can be successfully processed and it will not change
    member properties.
    """
    appointment = scheduled_appointment
    disconnected_at = (
        (appointment.scheduled_start + datetime.timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )
    data = {"practitioner_disconnected_at": disconnected_at}

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.practitioner),
    )
    data = api_helpers.load_json(res)

    assert res.status_code == 200
    assert data["practitioner_started_at"] == disconnected_at
    assert appointment.json.get("practitioner_disconnect_times") == [disconnected_at]
    assert not data["member_started_at"]
    assert not appointment.json.get("member_disconnect_times")


def test_appointment_in_incomplete_state_will_not_process_disconnected_data(
    client,
    api_helpers,
    incomplete_appointment,
):
    """
    Tests that disconnected data will not be processed when appointment is in incomplete state.
    """
    appointment = incomplete_appointment
    disconnected_at = (
        (appointment.scheduled_start + datetime.timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )
    data = {"member_disconnected_at": disconnected_at}

    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )

    assert res.status_code == 200
    assert not appointment.json.get("practitioner_disconnect_times")
    assert not appointment.json.get("member_disconnect_times")


def test_appointment_can_process_cancellation_survey_recorded_answers(
    client,
    api_helpers,
    cancelled_appointment,
    valid_questionnaire_with_oid,
):
    """Test that cancellation survey's recorded answers can be processed"""
    with patch(
        "appointments.resources.appointment.AppointmentResource._process_cancellation_survey_answers"
    ) as mock_process_cancellation_survey_answers:
        questionnaire = valid_questionnaire_with_oid(oid="cancellation_survey")
        questions = questionnaire.question_sets[0].questions
        question = next(q for q in questions if q.type == QuestionTypes.CHECKBOX)
        appointment = cancelled_appointment
        recorded_answers = [
            {
                "question_id": question.id,
                "user_id": appointment.member.id,
                "answer_id": None,
                "appointment_id": appointment.api_id,
                "text": "sample text",
            },
        ]
        data = {
            "surveys": {
                "cancellation_survey": {
                    "recorded_answers": recorded_answers,
                }
            }
        }

        res = client.put(
            f"/api/v1/appointments/{appointment.api_id}",
            data=json.dumps(data),
            headers=api_helpers.json_headers(appointment.member),
        )

        assert res.status_code == 200
        assert mock_process_cancellation_survey_answers.called


def test_update_rx_info_in_appointment(
    client,
    api_helpers,
    put_appointment_on_endpoint,
    basic_appointment,
    datetime_now_iso_format,
    datetime_one_hour_later_iso_format,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(APPOINTMENT_ALLOW_RX_OVERWRITE).value_for_all(True)
    )

    data = {"rx_written_at": datetime_now_iso_format, "rx_written_via": "call"}
    res = put_appointment_on_endpoint(
        api_id=basic_appointment.api_id,
        user=basic_appointment.practitioner,
        data_json_string=json.dumps(data),
    )
    assert res.status_code == 200
    res_data = api_helpers.load_json(res)
    assert res_data["rx_written_via"] == "call"
    assert res_data["rx_written_at"] is not None
    existing_rx_written_at = res_data["rx_written_at"]

    # The PUT appointment endpoint ignores rx_written_at in the request and sets the value to datetime.utcnow().
    # Without sleeping for 1 second, the test might run too fast, resulting in the second PATCH call setting
    # rx_written_at to the same value as the first PATCH call. Then assertion that the second rx_written_at >
    # first rx_written_at would fail.
    sleep(1)
    updated_data = {
        "rx_written_at": datetime_one_hour_later_iso_format,
        "rx_written_via": "dosespot",
    }
    res = put_appointment_on_endpoint(
        api_id=basic_appointment.api_id,
        user=basic_appointment.practitioner,
        data_json_string=json.dumps(updated_data),
    )
    assert res.status_code == 200
    res_data = api_helpers.load_json(res)
    assert res_data["rx_written_via"] == "dosespot"
    assert res_data["rx_written_at"] is not None
    assert res_data["rx_written_at"] > existing_rx_written_at


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_update_appointment_locale__error_processing_disconnected_at(
    locale,
    release_mono_api_localization_on,
    cancellable_appointment,
    client,
    api_helpers,
):
    data = {"practitioner_disconnected_at": datetime.datetime.utcnow().isoformat()}
    practitioner = cancellable_appointment.practitioner

    if locale is None:
        headers = api_helpers.json_headers(user=practitioner)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=practitioner), locale=locale
        )
    with mock.patch(
        "appointments.resources.appointment.AppointmentResource._process_disconnected_data",
        side_effect=Exception(),
    ):
        res = client.put(
            f"/api/v1/appointments/{cancellable_appointment.api_id}",
            data=api_helpers.json_data(data),
            headers=headers,
        )

    assert res.json["message"] != "appointment_disconnected_at_processing_error_message"


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_update_appointment_locale__error_processing_disconnected_at_member_survey(
    locale,
    release_mono_api_localization_on,
    cancellable_appointment,
    client,
    api_helpers,
):
    data = {"practitioner_disconnected_at": datetime.datetime.utcnow().isoformat()}
    practitioner = cancellable_appointment.practitioner

    if locale is None:
        headers = api_helpers.json_headers(user=practitioner)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=practitioner), locale=locale
        )
    with mock.patch(
        "appointments.resources.appointment.AppointmentResource._process_member_rating_disconnections",
        side_effect=Exception(),
    ):
        res = client.put(
            f"/api/v1/appointments/{cancellable_appointment.api_id}",
            data=api_helpers.json_data(data),
            headers=headers,
        )

    assert (
        res.json["message"]
        != "appointment_servey_disconnected_at_processing_error_message"
    )


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_update_appointment_locale__user_missing_pharmacy_info(
    locale,
    release_mono_api_localization_on,
    appointment_with_practitioner_enabled_for_prescribing,
    api_helpers,
    client,
):
    appointment = appointment_with_practitioner_enabled_for_prescribing()
    prac = appointment.practitioner
    if locale is None:
        headers = api_helpers.json_headers(user=prac)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=prac), locale=locale
        )

    with patch.object(
        DoseSpotAPI,
        "validate_pharmacy",
        return_value=({"PharmacyId": 1}),
    ):

        data = {"prescription_info": {"pharmacy_id": 1}}
        res = client.put(
            f"/api/v1/appointments/{appointment.api_id}",
            data=api_helpers.json_data(data),
            headers=headers,
        )

    assert res.json["message"] != "prescription_missing_data_error_message"


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_update_appointment_locale__anonymous_appointment_pharmacy_error(
    locale,
    release_mono_api_localization_on,
    member_enabled_for_prescription,
    appointment_with_practitioner_enabled_for_prescribing,
    api_helpers,
    client,
):
    appointment = appointment_with_practitioner_enabled_for_prescribing(
        member_schedule=member_enabled_for_prescription.schedule
    )
    appointment.privacy = PRIVACY_CHOICES.anonymous
    prac = appointment.practitioner
    if locale is None:
        headers = api_helpers.json_headers(user=prac)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=prac), locale=locale
        )

    with patch.object(
        DoseSpotAPI,
        "validate_pharmacy",
        return_value=({"PharmacyId": 1}),
    ):

        data = {"prescription_info": {"pharmacy_id": 1}}
        res = client.put(
            f"/api/v1/appointments/{appointment.api_id}",
            data=api_helpers.json_data(data),
            headers=headers,
        )

    assert res.json["message"] != "anonymous_appointment_pharmacy_error_message"


@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
def test_update_appointment_locale__practitioner_not_enabled(
    locale,
    release_mono_api_localization_on,
    api_helpers,
    client,
    member_enabled_for_prescription,
    appointment_with_practitioner_enabled_for_prescribing,
    factories,
):
    appointment = appointment_with_practitioner_enabled_for_prescribing(
        member_schedule=member_enabled_for_prescription.schedule
    )
    prac = appointment.practitioner

    if locale is None:
        headers = api_helpers.json_headers(user=prac)
    else:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=prac), locale=locale
        )

    with patch.object(
        DoseSpotAPI,
        "validate_pharmacy",
        return_value=({"PharmacyId": 1}),
    ):
        with mock.patch(
            "providers.service.provider.ProviderService.enabled_for_prescribing",
            side_effect=[True, False],
        ):
            data = {"prescription_info": {"pharmacy_id": 1}}
            res = client.put(
                f"/api/v1/appointments/{appointment.api_id}",
                data=api_helpers.json_data(data),
                headers=headers,
            )

    assert res.json["message"] != "practitioner_not_enabled_error_message"
