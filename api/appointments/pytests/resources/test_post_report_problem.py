from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from appointments.services.common import obfuscate_appointment_id
from pytests.factories import EnterpriseUserFactory


@patch("appointments.resources.report_problem.log.info")
def test_post_report_problem(
    mock_warn_info,
    valid_appointment,
    client,
    api_helpers,
):
    # Given a valid appointment with reported problems
    appointment = valid_appointment()
    user = EnterpriseUserFactory.create()
    # when: we report the problems
    res = client.post(
        "/api/v1/video/report_problem",
        data=json.dumps(
            {
                "appointment_api_id": obfuscate_appointment_id(appointment.id),
                "zoom_session_id": "Za23zdf023",
                "option_ids": [{"id": 1}, {"id": 3}],
            }
        ),
        headers=api_helpers.json_headers(user),
    )
    # then: we should log to datadog
    assert res.status_code == 200
    mock_warn_info.assert_called_with(
        "Participant reported a problem on their video appointment",
        appointment_id=appointment.id,
        problems=[
            "I could not hear the other participant",
            "I could not see the other participant",
        ],
        user_id=user.id,
        role="member",
        zoom_session_id="Za23zdf023",
    )


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr", "fr_CA"],
)
@patch("appointments.resources.report_problem.log.info")
def test_post_report_problem__appt_not_found(
    mock_warn_info,
    locale,
    client,
    api_helpers,
    default_user,
    release_mono_api_localization_on,
):
    # given: an appointment that doesn't exist

    # when we try to post
    headers = api_helpers.json_headers(default_user)
    if locale:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=default_user), locale=locale
        )
    res = client.post(
        "/api/v1/video/report_problem",
        data=json.dumps(
            {
                "appointment_api_id": "123456",
                "zoom_session_id": "Za23zdf023",
                "option_ids": [{"id": 1}, {"id": 3}],
            }
        ),
        headers=headers,
    )
    # then we should get an error
    assert res.status_code == 400
    assert mock_warn_info.assert_not_called
    res_data = api_helpers.load_json(res)
    assert res_data["message"] != "report_problem_app_missing"


@patch("appointments.resources.report_problem.log.info")
def test_post_report_problem__appt_field_wrong(
    mock_warn_info,
    client,
    api_helpers,
    default_user,
):
    # given: an appointment that doesn't exist

    # when we try to post
    res = client.post(
        "/api/v1/video/report_problem",
        data=json.dumps(
            {
                "appointment_id": "123456",
                "zoom_session_id": "Za23zdf023",
                "option_ids": [{"id": 1}, {"id": 3}],
            }
        ),
        headers=api_helpers.json_headers(default_user),
    )
    # then we should get an error
    assert res.status_code == 400
    assert mock_warn_info.assert_not_called
    res_data = api_helpers.load_json(res)
    assert res_data["message"] == "Appointment ID is missing or incorrect"
