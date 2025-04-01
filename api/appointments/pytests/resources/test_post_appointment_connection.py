import json
from datetime import datetime, timezone
from unittest import mock

import pytest

from appointments.schemas.appointment_connection import (
    HEARTBEAT_CONNECTION_INTERVAL_DEFAULT,
    HEARTBEAT_CONNECTION_PATH,
    AppointmentConnectionType,
    HeartbeatConnectionSchema,
    LaunchConfigurationSchema,
    VideoPlatform,
)


@pytest.mark.parametrize(
    "request_user",
    [
        ("member", 200),
        ("practitioner", 200),
    ],
)
@mock.patch(
    "appointments.services.video_connection.get_video_platform_access_token_for_appointment_session",
    return_value="mock_video_token",
)
@mock.patch(
    "appointments.services.video.zoom.generate_session_id",
    return_value="mock_zoom_session_id",
)
def test_post_appointment_connection(
    mock_zoom_generate_session_id,
    mock_get_video_platform_session_id_for_appointment,
    request_user,
    factories,
    client,
    api_helpers,
):
    # generate a User and Practitioner objs as we require these to fulfill Appointment's Product and Schedule relationships
    user_member = factories.DefaultUserFactory.create()
    user_practitioner = factories.PractitionerUserFactory.create()

    default_user = user_member if (request_user == "member") else user_practitioner

    member_schedule = factories.ScheduleFactory.create(user=user_member)
    product = factories.ProductFactory.create(practitioner=user_practitioner)

    appt_video = {"member_token": "456", "practitioner_token": "789"}

    appt = factories.AppointmentFactory.create(
        member_schedule=member_schedule,
        product=product,
        scheduled_start=datetime.now(timezone.utc),
        scheduled_end=datetime.now(timezone.utc),
        video=appt_video,
    )

    data = {
        "capabilities": "zoom",
        "device_type": "ios",
    }

    res = client.post(
        f"/api/v1/appointments/{appt.api_id}/connection",
        data=json.dumps(data),
        headers=api_helpers.json_headers(default_user),
    )
    assert res.status_code == 200

    data_dict = json.loads(res.data.decode("utf8"))
    heartbeat = HeartbeatConnectionSchema(**data_dict["heartbeat"])
    launch_config = LaunchConfigurationSchema(**data_dict["launch_configuration"])

    assert heartbeat.period_millis == HEARTBEAT_CONNECTION_INTERVAL_DEFAULT
    assert heartbeat.heartbeat_path == HEARTBEAT_CONNECTION_PATH.format(
        appointment_api_id=appt.api_id,
    )

    assert launch_config.connection_type == AppointmentConnectionType.VIDEO

    # Assert correct session id based on capabilities and if session exists in appt.video
    assert launch_config.video_platform == VideoPlatform.ZOOM
    # expect session_id from zoom.generate_session_id
    assert launch_config.session_id == "mock_zoom_session_id"

    # expect the token from video_connection, not the one from appointment.video
    assert launch_config.token == "mock_video_token"
    assert launch_config.api_key is None
