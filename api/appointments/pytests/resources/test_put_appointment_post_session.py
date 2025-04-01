from http import HTTPStatus

import pytest
from sqlalchemy import asc

from appointments.models.appointment_meta_data import AppointmentMetaData
from messaging.models.messaging import Message
from models.verticals_and_specialties import CX_VERTICAL_NAME


@pytest.mark.parametrize(
    "appointment_fixture",
    [
        "scheduled_appointment",
        "started_appointment",
        "ended_appointment",
    ],
)
def test_put_appointment_post_session_draft_and_then_final(
    put_appointment_post_session_on_endpoint,
    appointment_fixture,
    request,
):
    """Tests PUTting a draft post session note onto an appointment,
    and then updating the post session note with a final version.
    """
    # Get the specified appointment fixture
    appointment = request.getfixturevalue(appointment_fixture)

    # PUT the draft on the appointment
    post_session_note = "This is a draft"
    res = put_appointment_post_session_on_endpoint(
        appointment=appointment,
        post_session_note=post_session_note,
        is_draft=True,
    )

    # Assert successful status and note and message states
    assert res.status_code == HTTPStatus.OK
    _assert_draft_note_and_no_messages(note_content=post_session_note)

    # PUT the non-draft on the appointment
    post_session_note = "This is a final note"
    res = put_appointment_post_session_on_endpoint(
        appointment=appointment,
        post_session_note=post_session_note,
        is_draft=False,
    )

    # Assert successful status and note and message states
    assert res.status_code == HTTPStatus.OK
    _assert_non_draft_note_and_messages(
        note_content=post_session_note,
        message_sender_id=appointment.practitioner.id,
    )


def test_create_post_session_note_ca_to_member(
    started_appointment,
    put_appointment_post_session_on_endpoint,
    factories,
    mock_zendesk,
):
    """Tests that if the practitioner is a care advocate, the
    post session note will cause a Zendesk ticket to be created.
    """
    # Create a care advocate vertical and assign it to the practitioner
    ca_vertical = factories.VerticalFactory.create(name=CX_VERTICAL_NAME)
    started_appointment.practitioner.practitioner_profile.verticals.append(ca_vertical)

    # PUT the care advocate message on the appointment
    post_session_note = "Care advocate message..."
    res = put_appointment_post_session_on_endpoint(
        appointment=started_appointment,
        post_session_note=post_session_note,
        is_draft=False,
    )

    # Assert successful status and note and message states
    assert res.status_code == HTTPStatus.OK
    _assert_non_draft_note_and_messages(
        note_content=post_session_note,
        message_sender_id=started_appointment.practitioner.id,
    )

    # Assert that Mocked Zendesk Ticket is created with post session comment
    assert len(mock_zendesk._zd_comments) == 1
    assert len(mock_zendesk._zd_tickets) == 1


def _assert_draft_note_and_no_messages(note_content):
    """Asserts that the appointment has a draft post session note with the
    supplied content and that it did not create a message.
    """
    notes = AppointmentMetaData.query.order_by(
        asc(AppointmentMetaData.created_at)
    ).all()
    assert len(notes) == 1
    assert notes[0].content == note_content
    assert notes[0].draft

    message = Message.query.all()
    assert len(message) == 0


def _assert_non_draft_note_and_messages(note_content, message_sender_id):
    """Asserts that the appointment has a post session note with the
    supplied content and that it created a message that contains the same
    content.
    """
    notes = AppointmentMetaData.query.order_by(
        asc(AppointmentMetaData.created_at)
    ).all()
    assert len(notes) == 1
    assert notes[0].content == note_content
    assert not notes[0].draft

    message = Message.query.all()
    assert len(message) == 1
    assert note_content in message[0].body
    assert message[0].user_id == message_sender_id

    assert message[0].id == notes[0].message_id


def test_save_duplicate_drafts(
    put_appointment_post_session_on_endpoint, api_helpers, ended_appointment
):
    """
    test saving dupe post-session notes
    """
    appointment = ended_appointment
    post_session_note = "This is the a note"
    res = put_appointment_post_session_on_endpoint(
        appointment=appointment, post_session_note=post_session_note, is_draft=False
    )
    data = api_helpers.load_json(res)
    # Assert successful status and note and message states
    assert res.status_code == HTTPStatus.OK
    _assert_non_draft_note_and_messages(
        note_content=post_session_note,
        message_sender_id=appointment.practitioner.id,
    )
    assert data["post_session"]["created_at"]

    data["post_session"]["notes"] = post_session_note
    res3 = put_appointment_post_session_on_endpoint(
        appointment=appointment, post_session_note=post_session_note, is_draft=False
    )
    assert res3.status_code == 200

    assert (
        AppointmentMetaData.query.filter(
            AppointmentMetaData.appointment_id == appointment.id
        ).count()
        == 1
    )


def test_member_cannot_overwrite_post_session_note(
    client,
    api_helpers,
    scheduled_appointment,
):
    """Asserts that the member cannot override the post appointment note"""
    appointment = scheduled_appointment
    member = appointment.member
    practitioner = appointment.practitioner
    practitioner_note = "Note from practitioner"
    member_note = "Note from member"

    res = client.get(
        f"/api/v1/appointments/{appointment.api_id}",
        headers=api_helpers.json_headers(member),
    )
    data = api_helpers.load_json(res)

    data["post_session"]["notes"] = practitioner_note
    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(practitioner),
    )
    data = api_helpers.load_json(res)
    assert data["post_session"]["notes"] == practitioner_note

    data["post_session"]["notes"] = member_note
    res = client.put(
        f"/api/v1/appointments/{appointment.api_id}",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(member),
    )
    data = api_helpers.load_json(res)
    assert data["post_session"]["notes"] == practitioner_note
