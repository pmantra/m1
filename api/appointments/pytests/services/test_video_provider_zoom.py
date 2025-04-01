from __future__ import annotations

from unittest import mock

import jwt
import pytest

from appointments.services.video_provider.errors import RequiredParameterException
from appointments.services.video_provider.zoom import (
    MAX_ZOOM_SESSION_ID_LEN,
    ZOOM_SDK_SECRET,
    generate_access_token,
    generate_session_id,
    session_id_env_prefix_for_env,
)
from common.constants import Environment


def test_MAX_ZOOM_SESSION_ID_LEN():
    # this value is set by zoom and must not exceed 200
    assert MAX_ZOOM_SESSION_ID_LEN == 200


@pytest.mark.parametrize(
    "session_id",
    [
        None,
        "",
    ],
)
def test_generate_session_id_param_validation(session_id):
    with pytest.raises(RequiredParameterException):
        generate_session_id(session_id)


@pytest.mark.parametrize(
    ("env", "expected_prefix"),
    [
        (Environment.LOCAL, "local"),
        (Environment.QA1, "qa1"),
        (Environment.QA2, "qa2"),
        (Environment.QA3, "qa3"),
        (Environment.SANDBOX, "sand"),
        (Environment.STAGING, "stag"),
        (Environment.PRODUCTION, "p"),
        ("lolwut", "unknown"),
    ],
)
def test_session_id_env_prefix_for_env(env, expected_prefix):
    assert expected_prefix == session_id_env_prefix_for_env(env)


@mock.patch("appointments.services.video_provider.zoom.session_id_env_prefix_for_env")
@mock.patch("appointments.services.video_provider.zoom.hashlib")
def test_generate_session_id(mock_hashlib, mock_session_id_env_prefix_for_env):
    mock_hashlib.md5().hexdigest.return_value = "cool_hash"
    mock_session_id_env_prefix_for_env.return_value = "prefix"
    sesh_id = generate_session_id("some_appt_id")
    assert sesh_id == "cool_hash"
    # not the `b` we expect a byte string
    mock_hashlib.md5.assert_any_call(b"prefix-maven-some_appt_id")
    mock_hashlib.md5().hexdigest.assert_called_once()


@mock.patch("appointments.services.video_provider.zoom.hashlib")
def test_generate_session_id_max_len(mock_hashlib):
    mock_hashlib.md5().hexdigest.return_value = "x" * 300  # exceeds max length
    sesh_id = generate_session_id("some_appt_id")
    assert len(sesh_id) == MAX_ZOOM_SESSION_ID_LEN


@pytest.mark.parametrize(
    ["appointment_id", "session_id", "user_id"],
    [
        (None, None, None),
        (None, "", None),
        ("", "", None),
        ("", None, None),
    ],
)
def test_generate_access_token_param_validation(
    appointment_id: str | None,
    session_id: str | None,
    user_id: str | None,
):
    with pytest.raises(RequiredParameterException):
        generate_access_token(appointment_id, session_id, user_id)


def test_generate_access_token():
    token = generate_access_token("some_appt_id", "some_session_id", 123)
    decoded = jwt.decode(
        token,
        ZOOM_SDK_SECRET,
        algorithms=["HS256"],
        options={
            "verify_signature": True,
        },
    )
    assert decoded["tpc"] == "some_session_id"
    assert decoded["user_identity"] == "123"


def test_generate_access_token_without_userid():
    token = generate_access_token(12345, "some_session_id", None)
    decoded = jwt.decode(
        token,
        ZOOM_SDK_SECRET,
        algorithms=["HS256"],
        options={
            "verify_signature": True,
        },
    )
    assert decoded["tpc"] == "some_session_id"
    assert decoded["user_identity"] is None
