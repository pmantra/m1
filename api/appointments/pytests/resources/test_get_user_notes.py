import datetime
import json
from http import HTTPStatus

import pytest
from maven import feature_flags

from models.questionnaires import ASYNC_ENCOUNTER_QUESTIONNAIRE_OID
from models.verticals_and_specialties import (
    BIRTH_PLANNING_VERTICAL_NAME,
    CX_VERTICAL_NAME,
)
from pytests.factories import QuestionnaireFactory, VerticalFactory


@pytest.fixture
def ff_test_data():
    with feature_flags.test_data() as td:
        yield td


@pytest.fixture
def create_vertical():
    def create_vertical_func(vertical: str):
        if vertical == CX_VERTICAL_NAME:
            return VerticalFactory.create_cx_vertical()
        else:
            return VerticalFactory(name=vertical)

    return create_vertical_func


@pytest.fixture
def practitioner(factories, create_vertical):
    return factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[create_vertical(BIRTH_PLANNING_VERTICAL_NAME)],
    )


@pytest.fixture
def cx_practitioner(factories, create_vertical):
    return factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[create_vertical(CX_VERTICAL_NAME)],
    )


@pytest.fixture
def appointment_1(factories, practitioner, datetime_one_hour_earlier):
    return factories.AppointmentFactory.create_with_practitioner(
        practitioner=practitioner,
        scheduled_start=datetime_one_hour_earlier + datetime.timedelta(minutes=1),
        scheduled_end=datetime_one_hour_earlier + datetime.timedelta(minutes=30),
    )


@pytest.fixture
def appointment_2(appointment_1, factories, practitioner, datetime_one_hour_later):
    """Creates an appointment using the same member_schedule as
    appointment_1
    """
    return factories.AppointmentFactory.create_with_practitioner(
        practitioner=practitioner,
        member_schedule=appointment_1.member_schedule,
        scheduled_start=datetime_one_hour_later + datetime.timedelta(minutes=1),
        scheduled_end=datetime_one_hour_later + datetime.timedelta(minutes=30),
    )


@pytest.fixture
def appointment_3(appointment_1, factories, cx_practitioner, datetime_now):
    """Creates an appointment using the same member_schedule as
    appointment_1
    """
    datetime_two_hours_later = datetime_now + datetime.timedelta(hours=2)
    return factories.AppointmentFactory.create_with_practitioner(
        practitioner=cx_practitioner,
        member_schedule=appointment_1.member_schedule,
        scheduled_start=datetime_now - datetime.timedelta(hours=2),
        scheduled_end=datetime_two_hours_later + datetime.timedelta(minutes=30),
    )


@pytest.fixture
def appointment_4(appointment_1, factories, practitioner, datetime_one_hour_earlier):
    """Creates a completed appointment using the same member_schedule as
    appointment_1
    """
    appointment = factories.AppointmentFactory.create_with_practitioner(
        practitioner=practitioner,
        member_schedule=appointment_1.member_schedule,
        scheduled_start=datetime_one_hour_earlier,
        scheduled_end=datetime_one_hour_earlier + datetime.timedelta(minutes=30),
    )
    appointment.practitioner_started_at = datetime_one_hour_earlier
    appointment.practitioner_ended_at = datetime_one_hour_earlier + datetime.timedelta(
        minutes=30
    )
    appointment.member_started_at = datetime_one_hour_earlier
    appointment.member_ended_at = datetime_one_hour_earlier + datetime.timedelta(
        minutes=30
    )
    return appointment


@pytest.fixture
def appointment_5(appointment_1, factories, practitioner, datetime_one_hour_later):
    """Creates a complete and cancelled appointment using the same member_schedule as
    appointment_1
    """
    appointment = factories.AppointmentFactory.create_with_practitioner(
        practitioner=practitioner,
        member_schedule=appointment_1.member_schedule,
        scheduled_start=datetime_one_hour_later,
        scheduled_end=datetime_one_hour_later + datetime.timedelta(minutes=30),
    )
    appointment.practitioner_started_at = datetime_one_hour_later
    appointment.practitioner_ended_at = datetime_one_hour_later + datetime.timedelta(
        minutes=30
    )
    appointment.member_started_at = datetime_one_hour_later
    appointment.member_ended_at = datetime_one_hour_later + datetime.timedelta(
        minutes=30
    )
    appointment.cancelled_at = datetime_one_hour_later + datetime.timedelta(minutes=30)
    return appointment


@pytest.fixture
def no_note_appointment(
    appointment_1, factories, cx_practitioner, datetime_one_hour_later
):
    """Creates an appointment using the same member_schedule as
    appointment_1
    """
    return factories.AppointmentFactory.create_with_practitioner(
        practitioner=cx_practitioner,
        member_schedule=appointment_1.member_schedule,
        scheduled_start=datetime_one_hour_later - datetime.timedelta(minutes=2),
        scheduled_end=datetime_one_hour_later + datetime.timedelta(minutes=30),
    )


@pytest.fixture
def add_appts_and_notes(
    factories, appointment_1, appointment_2, appointment_3, appointment_4, appointment_5
):
    """Sets separate notes for appointment_1 and appointment_2.
    This is to test note sharing between appointments.
    """
    factories.AppointmentMetaDataFactory.create(
        appointment_id=appointment_1.id, content="note 1"
    )
    factories.AppointmentMetaDataFactory.create(
        appointment_id=appointment_2.id, content="note 2"
    )
    factories.AppointmentMetaDataFactory.create(
        appointment_id=appointment_3.id, content="note 3"
    )
    factories.AppointmentMetaDataFactory.create(
        appointment_id=appointment_4.id, content="note 4"
    )
    factories.AppointmentMetaDataFactory.create(
        appointment_id=appointment_5.id, content="note 5"
    )


@pytest.fixture
def get_user_notes_from_endpoint(client, api_helpers):
    def get_user_notes_from_endpoint_func(
        user_id,
        practitioner,
        filter={},  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    ):
        return client.get(
            f"/api/v1/users/{user_id}/notes",
            query_string=filter,
            headers=api_helpers.json_headers(user=practitioner),
        )

    return get_user_notes_from_endpoint_func


@pytest.mark.usefixtures("add_appts_and_notes")
def test_no_note_sharing(appointment_1, get_user_notes_from_endpoint):
    """Tests that only notes for the logged in practitioner are returned if
    opted_in_notes_sharing is False (which is the default case).
    """
    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
    )
    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 4
    assert [apt["post_session"]["notes"] for apt in body["data"]] == [
        "note 2",
        "note 5",
        "note 1",
        "note 4",
    ]


@pytest.mark.usefixtures("add_appts_and_notes")
def test_note_sharing(appointment_1, get_user_notes_from_endpoint):
    """Tests that notes for the all the appointments are returned if
    opted_in_notes_sharing is True and in desc chronological order.
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = True

    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
    )
    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 5
    assert [apt["post_session"]["notes"] for apt in body["data"]] == [
        "note 2",
        "note 5",
        "note 1",
        "note 4",
        "note 3",
    ]


@pytest.mark.usefixtures("add_appts_and_notes")
def test_exclude_async_encounter_note(appointment_1, get_user_notes_from_endpoint):
    """
    Tests that structured internal note for async encounter oids do not return
    """
    vertical = appointment_1.practitioner.practitioner_profile.verticals[0]
    QuestionnaireFactory.create(
        oid=ASYNC_ENCOUNTER_QUESTIONNAIRE_OID + "_care_advocate", verticals=[vertical]
    )
    questionnaire = QuestionnaireFactory.create(verticals=[vertical])
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = True

    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
    )
    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 5
    assert body["data"][0]["structured_internal_note"]["questionnaire"]["id"] == str(
        questionnaire.id
    )


@pytest.mark.usefixtures("add_appts_and_notes")
def test_note_my_appointments_filter(appointment_1, get_user_notes_from_endpoint):
    """Tests that only the logged-in practitioner's notes are returned
    if the practitioner filters by my_appointments
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = True

    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"my_appointments": True},
    )

    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 4
    assert [apt["post_session"]["notes"] for apt in body["data"]] == [
        "note 2",
        "note 5",
        "note 1",
        "note 4",
    ]


@pytest.mark.usefixtures("add_appts_and_notes")
def test_note_my_encounters_filter_async_flag_on(
    appointment_1, get_user_notes_from_endpoint, ff_test_data
):
    """Tests that only the logged-in practitioner's notes are returned
    if the practitioner filters by my_encounters
    TODO cleanup flags MPC-3795
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = True

    ff_test_data.update(
        ff_test_data.flag("release-mpractice-async-encounters").variation_for_all(True)
    )
    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"my_encounters": True},
    )

    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 4
    assert [apt["post_session"]["notes"] for apt in body["data"]] == [
        "note 2",
        "note 5",
        "note 1",
        "note 4",
    ]


@pytest.mark.usefixtures("add_appts_and_notes")
def test_no_note_sharing_no_my_appointments(
    appointment_1, get_user_notes_from_endpoint
):
    """Tests that notes for only the current logged-in practitioner
    are returned if opted_in_notes_sharing is False, even if my_appointments
    is not set to true.
    TODO cleanup flags MPC-3795
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = False

    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"my_appointments": False},
    )
    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 4
    assert [apt["post_session"]["notes"] for apt in body["data"]] == [
        "note 2",
        "note 5",
        "note 1",
        "note 4",
    ]


@pytest.mark.usefixtures("add_appts_and_notes")
def test_no_note_sharing_no_my_encounters_async_flag_on(
    appointment_1, get_user_notes_from_endpoint, ff_test_data
):
    """Tests that notes for only the current logged-in practitioner
    are returned if opted_in_notes_sharing is False, even if my_encounters
    is not set to true.
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = False

    ff_test_data.update(
        ff_test_data.flag("release-mpractice-async-encounters").variation_for_all(True)
    )
    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"my_encounters": False},
    )
    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 4
    assert [apt["post_session"]["notes"] for apt in body["data"]] == [
        "note 2",
        "note 5",
        "note 1",
        "note 4",
    ]


@pytest.mark.usefixtures("add_appts_and_notes")
@pytest.mark.parametrize(
    argnames="scheduled_start,scheduled_end",
    argvalues=[
        (
            datetime.datetime.utcnow() - datetime.timedelta(days=1),
            None,
        ),
        (
            datetime.datetime.utcnow() + datetime.timedelta(days=1),
            None,
        ),
        (
            None,
            datetime.datetime.utcnow() - datetime.timedelta(days=1),
        ),
        (
            None,
            datetime.datetime.utcnow() + datetime.timedelta(days=1),
        ),
        (
            datetime.datetime.utcnow() - datetime.timedelta(days=1),
            datetime.datetime.utcnow() + datetime.timedelta(days=1),
        ),
    ],
    ids=[
        "start-yesterday",
        "start-tomorrow",
        "end-yesterday",
        "end-tomorrow",
        "start-yesterday-end-tomorrow",
    ],
)
def test_notes_filtered_by_date(
    appointment_1, get_user_notes_from_endpoint, scheduled_start, scheduled_end
):
    """
    Tests that notes filtered by dates are returned when the filter is provided
    """
    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"scheduled_start": scheduled_start, "scheduled_end": scheduled_end},
    )
    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)["data"]

    for n in body:
        if scheduled_start:
            assert n["scheduled_start"] >= scheduled_start.isoformat()
        if scheduled_end:
            assert n["scheduled_end"] <= scheduled_end.isoformat()


@pytest.mark.usefixtures("add_appts_and_notes")
def test_note_completed_appointments_filter(
    appointment_4, get_user_notes_from_endpoint
):
    """
    Tests that completed appointment notes, excluding cancelled appointments,
    are filtered when completed_appointments param is passed
    """

    res = get_user_notes_from_endpoint(
        user_id=appointment_4.member_schedule.user_id,
        practitioner=appointment_4.practitioner,
        filter={"completed_appointments": True},
    )

    assert res.status_code == HTTPStatus.OK

    body = json.loads(res.data)
    assert len(body["data"]) == 1
    assert body["data"][0]["post_session"]["notes"] == "note 4"


@pytest.mark.usefixtures("add_appts_and_notes")
def test_note_all_appointments_filter(
    appointment_1, get_user_notes_from_endpoint, no_note_appointment
):
    """
    Tests that notes for all appointments regardless of
    if there is a note or not appear
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = True

    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"all_appointments": True},
    )

    assert res.status_code == HTTPStatus.OK
    body = json.loads(res.data)
    assert len(body["data"]) == 6
    assert [apt["post_session"]["notes"] for apt in body["data"]] == [
        "note 2",
        "note 5",
        "",
        "note 1",
        "note 4",
        "note 3",
    ]


@pytest.mark.usefixtures("add_appts_and_notes")
def test_single_vertical_filter(
    create_vertical, practitioner, appointment_1, get_user_notes_from_endpoint
):
    """Tests that notes only matching the specified single vertical
    are returned.
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = True

    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"provider_types": ["Care Advocate"]},
    )

    assert res.status_code == HTTPStatus.OK
    body = json.loads(res.data)
    assert len([e for e in body["data"] if isinstance(e, dict)]) == 1


@pytest.mark.usefixtures("add_appts_and_notes")
def test_multiple_vertical_filter(
    create_vertical, practitioner, appointment_1, get_user_notes_from_endpoint
):
    """Tests that notes only matching the specified single vertical
    are returned.
    """
    appointment_1.member.member_profile.json["opted_in_notes_sharing"] = True

    res = get_user_notes_from_endpoint(
        user_id=appointment_1.member_schedule.user_id,
        practitioner=appointment_1.practitioner,
        filter={"provider_types": ["Birth Planning", "Care Advocate"]},
    )

    assert res.status_code == HTTPStatus.OK
    body = json.loads(res.data)
    assert len([e for e in body["data"] if isinstance(e, dict)]) == 5
