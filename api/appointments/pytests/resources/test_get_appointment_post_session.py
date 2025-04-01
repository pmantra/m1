from http import HTTPStatus

import pytest
from maven import feature_flags


@pytest.fixture
def ff_test_data():
    with feature_flags.test_data() as td:
        yield td


@pytest.mark.parametrize(
    "enable_hide_post_session_notes_draft_flag_value",
    [True, False],
)
def test_get_post_session_note_empty_note_practitioner(
    basic_appointment,
    get_appointment_from_endpoint_using_appointment,
    enable_hide_post_session_notes_draft_flag_value,
    get_post_session_dict_in_response,
    ff_test_data,
):
    """Tests that a basic appointment has no post session note"""
    ff_test_data.update(
        ff_test_data.flag(
            "release-hide-post-session-notes-draft-from-members"
        ).variation_for_all(enable_hide_post_session_notes_draft_flag_value)
    )

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and the expected note: None
    assert res.status_code == HTTPStatus.OK
    assert res.json["post_session"] == get_post_session_dict_in_response()


@pytest.mark.parametrize(
    "enable_hide_post_session_notes_draft_flag_value",
    [True, False],
)
def test_get_appointment_post_session_practitioner(
    basic_appointment,
    add_appointment_post_session_note,
    datetime_one_hour_earlier,
    datetime_now,
    get_appointment_from_endpoint_using_appointment,
    enable_hide_post_session_notes_draft_flag_value,
    get_post_session_dict_in_response,
    add_non_draft_appointment_post_session_note,
    ff_test_data,
):
    """Tests that the appointment information will have the most recent note"""
    ff_test_data.update(
        ff_test_data.flag(
            "release-hide-post-session-notes-draft-from-members"
        ).variation_for_all(enable_hide_post_session_notes_draft_flag_value)
    )
    # Add first note
    add_non_draft_appointment_post_session_note(
        appointment=basic_appointment,
        content="Do the thing.",
        created_at=datetime_one_hour_earlier,
        modified_at=datetime_one_hour_earlier,
    )
    # Add second note (draft)
    latest_note = add_appointment_post_session_note(
        appointment=basic_appointment,
        content="Do the thing more recently",
        created_at=datetime_now,
        modified_at=datetime_now,
    )

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and the expected note: latest_note regardless if it's a draft
    assert res.status_code == HTTPStatus.OK
    assert res.json["post_session"] == get_post_session_dict_in_response(
        appointment_meta_data=latest_note
    )


@pytest.mark.parametrize(
    "enable_hide_post_session_notes_draft_flag_value",
    [True, False],
)
def test_get_appointment_post_session_member_hide_draft_flag(
    basic_appointment,
    add_appointment_post_session_note,
    add_non_draft_appointment_post_session_note,
    datetime_one_hour_earlier,
    datetime_now,
    get_appointment_from_endpoint_using_appointment_user_member,
    enable_hide_post_session_notes_draft_flag_value,
    get_post_session_dict_in_response,
    ff_test_data,
):
    """Tests that the appointment information will have the most recent note"""
    ff_test_data.update(
        ff_test_data.flag(
            "release-hide-post-session-notes-draft-from-members"
        ).variation_for_all(enable_hide_post_session_notes_draft_flag_value)
    )
    # Add first note
    first_note = add_non_draft_appointment_post_session_note(
        appointment=basic_appointment,
        content="Do the thing.",
        created_at=datetime_one_hour_earlier,
        modified_at=datetime_one_hour_earlier,
    )
    # Add second note (draft)
    second_note = add_appointment_post_session_note(
        appointment=basic_appointment,
        content="Do the thing more recently",
        created_at=datetime_now,
        modified_at=datetime_now,
    )

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment_user_member(basic_appointment)

    # Assert a successful GET
    assert res.status_code == HTTPStatus.OK
    # When the flag is on, return first_note (not a draft)
    if enable_hide_post_session_notes_draft_flag_value:
        assert res.json["post_session"] == get_post_session_dict_in_response(
            appointment_meta_data=first_note
        )
    # When the flag is off, return the second note (regardless if it's a draft)
    else:
        assert res.json["post_session"] == get_post_session_dict_in_response(
            appointment_meta_data=second_note
        )


@pytest.mark.parametrize(
    "enable_hide_post_session_notes_draft_flag_value",
    [True, False],
)
def test_get_post_session_note_empty_note_member(
    basic_appointment,
    get_appointment_from_endpoint_using_appointment_user_member,
    enable_hide_post_session_notes_draft_flag_value,
    get_post_session_dict_in_response,
    ff_test_data,
):
    """Tests that a basic appointment has no post session note"""
    ff_test_data.update(
        ff_test_data.flag(
            "release-hide-post-session-notes-draft-from-members"
        ).variation_for_all(enable_hide_post_session_notes_draft_flag_value)
    )

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment_user_member(basic_appointment)

    # Assert a successful GET and the expected note: None
    assert res.status_code == HTTPStatus.OK
    assert res.json["post_session"] == get_post_session_dict_in_response()
