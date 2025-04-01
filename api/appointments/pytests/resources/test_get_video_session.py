from __future__ import annotations

from unittest import mock

import pytest

from common.constants import Environment


@mock.patch(
    "appointments.resources.video.Environment.current",
    return_value=Environment.PRODUCTION,
)
def test_get_video_session_v1__prod_env(
    mock_current_env,
    client,
    api_helpers,
    default_user,
):
    # Given prod env

    # When hitting v1 /session
    res = client.get(
        "/api/v1/video/session",
        headers=api_helpers.json_headers(default_user),
    )
    # Then expect 403
    assert res.status_code == 403


@mock.patch(
    "appointments.resources.video.Environment.current",
    return_value=Environment.PRODUCTION,
)
def test_get_video_session_v2__prod_env(
    mock_current_env,
    client,
    api_helpers,
    default_user,
):
    # Given prod env

    # When hitting v2 /session
    appt_id = 123
    video_platform = "zoom"
    res = client.get(
        f"/api/v2/video/session?vp={video_platform}&oaid={appt_id}",
        headers=api_helpers.json_headers(default_user),
    )
    # Then expect 403
    assert res.status_code == 403


@mock.patch(
    "appointments.services.video_provider.zoom.generate_session_id",
    return_value="zoom_sesh",
)
def test_get_video_session_v2_by_platform(
    mock_zoom_generate_session_id,
    client,
    api_helpers,
    default_user,
):
    # Given non prod env

    # When hitting v2 /session
    appt_id = 123
    res = client.get(
        f"/api/v2/video/session?vp=zoom&oaid={appt_id}",
        headers=api_helpers.json_headers(default_user),
    )

    assert res.status_code == 200
    session_id = res.json["session_id"]
    assert session_id == "zoom_sesh"
    mock_zoom_generate_session_id.assert_called_once_with(appt_id)


@mock.patch(
    "appointments.resources.video.Environment.current",
    return_value=Environment.PRODUCTION,
)
def test_get_video_session_token_v1__prod_env(
    mock_current_env,
    client,
    api_helpers,
    default_user,
):
    # Given prod env

    # When hitting v1 /token
    res = client.get(
        "/api/v1/video/session/some_session_id/token",
        headers=api_helpers.json_headers(default_user),
    )

    # Then expect 403
    assert res.status_code == 403


@mock.patch(
    "appointments.resources.video.Environment.current",
    return_value=Environment.PRODUCTION,
)
def test_get_video_session_token_v2_by_platform__prod_env(
    mock_current_env,
    client,
    api_helpers,
    default_user,
):
    # Given prod env

    # When hitting v2 /token
    session_id = "1"
    video_platform = "zoom"

    res = client.get(
        f"/api/v2/video/session/{session_id}/token?vp={video_platform}&oaid=123",
        headers=api_helpers.json_headers(default_user),
    )

    # Then expect 403
    assert res.status_code == 403


@pytest.mark.parametrize(
    ["video_platform", "session_id", "expected_token"],
    [
        ("zoom", "zoom_sesh", "zoom_tok"),
    ],
)
@mock.patch(
    "appointments.services.video_provider.zoom.generate_access_token",
    return_value="zoom_tok",
)
def test_get_video_session_token_v2_by_platform__non_prod(
    mock_zoom_generate_access_token,
    video_platform,
    session_id,
    expected_token,
    client,
    api_helpers,
    default_user,
):
    # Given non prod env
    appt_id = 123
    # When hitting v2 /token
    res = client.get(
        f"/api/v2/video/session/{session_id}/token?vp={video_platform}&oaid={appt_id}",
        headers=api_helpers.json_headers(default_user),
    )

    # Then
    assert res.status_code == 200
    resp_session_id = res.json["session_id"]
    assert resp_session_id == session_id
    token = res.json["token"]
    assert token == expected_token
    mock_zoom_generate_access_token.assert_called_once_with(
        appointment_id=appt_id,
        session_id=session_id,
        optional_token_user_data=None,
        user_id=None,
    )
