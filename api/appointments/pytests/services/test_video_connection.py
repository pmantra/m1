from unittest import mock

import pytest

from appointments.schemas.appointment_connection import (
    HEARTBEAT_CONNECTION_INTERVAL_DEFAULT,
    HEARTBEAT_CONNECTION_PATH,
    AppointmentConnectionType,
    VideoPlatform,
)
from appointments.services.video_connection import (
    generate_heartbeat_config,
    generate_launch_configuration,
)
from authz.models.roles import ROLES


@mock.patch(
    "appointments.services.video_connection.get_video_platform_access_token_for_appointment_session",
    return_value="video_access_token",
)
@mock.patch(
    "appointments.services.video_connection.get_video_platform_session_id_for_appointment",
    return_value="mock_session_id",
)
def test_generate_launch_configuration(
    mock_session_id,
    mock_get_video_platform_access_token_for_appointment_session,
):

    launch_conf = generate_launch_configuration(
        appointment_id=123,
        user_id=123,
        user_role=ROLES.member,
    )
    mock_get_video_platform_access_token_for_appointment_session.assert_called()

    assert launch_conf.connection_type == AppointmentConnectionType.VIDEO
    assert launch_conf.video_platform == VideoPlatform.ZOOM
    assert launch_conf.session_id == "mock_session_id"
    assert launch_conf.token == "video_access_token"


def test_generate_heartbeat_config_without_fflag():
    hb_conf = generate_heartbeat_config(appointment_api_id=123)
    assert hb_conf.period_millis == HEARTBEAT_CONNECTION_INTERVAL_DEFAULT
    assert hb_conf.heartbeat_path == HEARTBEAT_CONNECTION_PATH.format(
        appointment_api_id=123,
    )


@mock.patch(
    "appointments.services.video_connection.feature_flags.int_variation",
)
def test_generate_heartbeat_config_with_fflag(mock_feature_flag):
    # Given
    mock_feature_flag.return_value = 10000
    hb_conf = generate_heartbeat_config(appointment_api_id=123)

    # Then
    assert hb_conf.period_millis == 10000
    assert hb_conf.heartbeat_path == HEARTBEAT_CONNECTION_PATH.format(
        appointment_api_id=123,
    )


@pytest.mark.parametrize(
    ("role_list", "expected_result"),
    [
        ([], None),
        ([ROLES.member], ROLES.member),
        ([ROLES.practitioner], ROLES.practitioner),
        # this is an unexpected case but this ensures we resolve consistently
        ([ROLES.member, ROLES.practitioner], ROLES.member),
        (
            [ROLES.payments_staff, ROLES.care_coordinator, ROLES.practitioner],
            ROLES.practitioner,
        ),
        (
            [
                ROLES.payments_staff,
                ROLES.care_coordinator,
                ROLES.fertility_clinic_billing_user,
            ],
            None,
        ),
    ],
)
def get_appointment_user_role(role_list, expected_result):
    assert get_appointment_user_role(role_list) == expected_result
