from __future__ import annotations

import json
from unittest import mock
from unittest.mock import patch

import pytest

from appointments.services.video_provider.zoom import generate_session_id


@patch("appointments.resources.zoom_webhook.log.warn")
@mock.patch(
    "appointments.resources.zoom_webhook.verify_zoom_signature",
    return_value=True,
)
def test_post_zoom_webhook__session_alert_request(
    mock_verify_zoom_signature,
    mock_log_warn,
    client,
    api_helpers,
    default_user,
):
    # Given
    appointment_id = 123
    session_id = generate_session_id(appointment_id=appointment_id)

    zoom_webhook_request = {
        "event": "session.alert",
        "event_ts": 1626473951859,
        "payload": {
            "account_id": "EFgHiJABC000DEfGHI",
            "object": {
                "id": "4567UVWxYZABCdEfGhiJkl==",
                "session_id": "123ladkfja==",
                "session_name": session_id,
                "session_key": "ABC36jaBI145",
                "issues": "Unstable audio quality",
            },
        },
    }
    # When
    res = client.post(
        "/api/v1/_/vendor/zoom/webhook",
        data=json.dumps(zoom_webhook_request),
        headers=api_helpers.json_headers(default_user),
    )
    # Then
    assert res.status_code == 200
    mock_log_warn.assert_called_with(
        "Issue encountered during the appointment",
        session_id=session_id,
        zoom_event="session.alert",
        issues="Unstable audio quality",
    )


@pytest.mark.parametrize(
    argnames="missing_param",
    argvalues=["session_name", "issues"],
)
@patch("appointments.resources.zoom_webhook.log.warn")
@mock.patch(
    "appointments.resources.zoom_webhook.verify_zoom_signature",
    return_value=True,
)
def test_post_zoom_webhook__no_session_or_issues(
    mock_verify_zoom_signature,
    mock_log_warn,
    missing_param,
    client,
    api_helpers,
    default_user,
):
    # Given
    session_name = "4567UVWxYZABCdEfGhiJkl=="
    zoom_webhook_request = {
        "event": "session.alert",
        "event_ts": 1626473951859,
        "payload": {
            "account_id": "EFgHiJABC000DEfGHI",
            "object": {
                "id": "4567UVWxYZABCdEfGhiJkl==",
                "session_id": "123ladkfja==",
                "session_name": session_name,
                "session_key": "ABC36jaBI145",
                "issues": "Unstable audio quality",
            },
        },
    }
    zoom_webhook_request["payload"]["object"].pop(missing_param)

    # When
    res = client.post(
        "/api/v1/_/vendor/zoom/webhook",
        data=json.dumps(zoom_webhook_request),
        headers=api_helpers.json_headers(default_user),
    )
    # Then
    assert res.status_code == 200
    mock_log_warn.assert_not_called()
