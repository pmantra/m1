import datetime
import json
from http import HTTPStatus

import pytest
from sqlalchemy import asc

from appointments.models.appointment_meta_data import AppointmentMetaData
from messaging.models.messaging import Message


@pytest.fixture
def put_legacy_appointment_post_session_on_endpoint(
    put_appointment_on_endpoint_using_appointment,
):
    """PUTs a legacy post session note on an appointment via the endpoint.
    Legacy code did not include a draft boolean.
    """

    def put_legacy_appointment_post_session_on_endpoint_func(
        appointment,
        post_session_note,
    ):
        # Create the data structure for the post session note
        post_session_data = {
            "id": appointment.api_id,
            "post_session": {
                "notes": post_session_note,
            },
        }

        # PUT the post session note on the appointment
        return put_appointment_on_endpoint_using_appointment(
            appointment=appointment,
            data_json_string=json.dumps(post_session_data),
            appointment_user=appointment.practitioner,
        )

    return put_legacy_appointment_post_session_on_endpoint_func


def test_put_post_session_note_without_draft_setting(
    frozen_now,
    basic_appointment,
    datetime_now_iso_format,
    put_legacy_appointment_post_session_on_endpoint,
):
    """Tests the legacy UI's call, which did not include a draft setting.
    The system should consider these as non-draft versions.
    """
    # PUT a post session note without using a draft flag
    post_session_note = "This is a legacy test"
    res = put_legacy_appointment_post_session_on_endpoint(
        appointment=basic_appointment,
        post_session_note=post_session_note,
    )

    # Assert that the endpoint call was successful and that the
    # post session notes were handled as expected.
    _assert_successful_put_appointment_post_session_notes(
        put_response=res,
        expected_data=[
            {
                "post_session_note": post_session_note,
                "is_draft": False,
                "created_at": datetime.datetime.utcnow(),
            },
        ],
        message_sender_id=basic_appointment.practitioner.id,
    )


def test_multiple_non_draft_post_session_notes(
    frozen_now,
    datetime_now,
    started_appointment,
    put_legacy_appointment_post_session_on_endpoint,
):
    """The old mPrac allowed multiple non-draft post session notes from
    one user. Notes were "updated" by adding a new note with a more
    recent created_at datetime.
    """
    # Add the first note
    existing_post_session_note = "Existing note"
    res = put_legacy_appointment_post_session_on_endpoint(
        appointment=started_appointment,
        post_session_note=existing_post_session_note,
    )

    # Assert that the endpoint call was successful and that the
    # post session notes were handled as expected.
    created_time = datetime.datetime.utcnow()
    expected_data = [
        {
            "post_session_note": existing_post_session_note,
            "is_draft": False,
            "created_at": created_time,
        },
    ]
    _assert_successful_put_appointment_post_session_notes(
        put_response=res,
        expected_data=expected_data,
        message_sender_id=started_appointment.practitioner.id,
    )

    # Move time forward
    frozen_now.shift(1)

    # Add the second note
    updated_post_session_note = "Updated note in old mPrac"
    res = put_legacy_appointment_post_session_on_endpoint(
        appointment=started_appointment,
        post_session_note=updated_post_session_note,
    )

    # Assert that the endpoint call was successful and that the
    # post session notes were handled as expected.
    expected_data = [
        {
            "post_session_note": updated_post_session_note,
            "is_draft": False,
            "created_at": created_time,
            "modified_at": datetime.datetime.utcnow(),
        }
    ]
    _assert_successful_put_appointment_post_session_notes(
        put_response=res,
        expected_data=expected_data,
        message_sender_id=started_appointment.practitioner.id,
    )


def test_allow_non_draft_post_session_note_to_be_updated_with_draft(
    frozen_now,
    datetime_now,
    started_appointment,
    put_legacy_appointment_post_session_on_endpoint,
    put_appointment_post_session_on_endpoint,
):
    """Tests that a draft post session note can "update" an existing
    non-draft post session note. The old system did not have a draft status,
    so all notes were considered non-draft post session notes. Notes were
    "updated" by adding a new note with a more recent created_at datetime.
    """
    # Add the first note
    existing_post_session_note = "Existing note that should be done"
    res = put_legacy_appointment_post_session_on_endpoint(
        appointment=started_appointment,
        post_session_note=existing_post_session_note,
    )

    # Assert that the endpoint call was successful and that the
    # post session notes were handled as expected.
    created_time = datetime.datetime.utcnow()
    expected_data = [
        {
            "post_session_note": existing_post_session_note,
            "is_draft": False,
            "created_at": created_time,
        },
    ]
    _assert_successful_put_appointment_post_session_notes(
        put_response=res,
        expected_data=expected_data,
        message_sender_id=started_appointment.practitioner.id,
    )

    # Move time forward
    frozen_now.shift(1)

    # Add the second note using is_draft set to True
    updated_post_session_note = "Updated note to allow for legacy UIs"
    res = put_appointment_post_session_on_endpoint(
        appointment=started_appointment,
        post_session_note=updated_post_session_note,
        is_draft=True,
    )

    # Assert that the endpoint call was successful and that the
    # post session notes were handled as expected.
    expected_data = [
        {
            "post_session_note": updated_post_session_note,
            "is_draft": True,
            "created_at": created_time,
            "modified_at": datetime.datetime.utcnow(),
        }
    ]
    _assert_successful_put_appointment_post_session_notes(
        put_response=res,
        expected_data=expected_data,
        message_sender_id=started_appointment.practitioner.id,
    )


def _assert_successful_put_appointment_post_session_notes(
    put_response,
    expected_data,
    message_sender_id=None,
):
    assert put_response.status_code == HTTPStatus.OK

    notes = AppointmentMetaData.query.order_by(
        asc(AppointmentMetaData.created_at)
    ).all()
    message = Message.query.all()

    message_body = ""
    for msg in message:
        message_body += msg.body

    assert len(notes) == 1
    message_idx = 0
    # Confirm each expected note is in the appointment notes and that the non-draft
    # notes created messages
    for idx, expected_datum in enumerate(expected_data):
        # Assert that the notes were added as expected.
        assert notes[idx].content == expected_datum["post_session_note"]
        assert notes[idx].draft == expected_datum["is_draft"]
        assert notes[idx].created_at == expected_datum["created_at"]

        if not expected_datum["is_draft"]:
            # Assert that the note created a message, since it is not considered a
            # draft note.
            assert message[message_idx].user_id == message_sender_id
            assert expected_datum["post_session_note"] in message_body
            message_idx += 1
