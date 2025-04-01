import datetime
import json

import pytest

from appointments.models.appointment import Appointment
from appointments.services.common import deobfuscate_appointment_id


@pytest.fixture
def mock_appointment(
    request, factories
):  # either return a new Appointment or None, based on the incoming parametrized value
    if request.param:
        user = factories.DefaultUserFactory.create()
        member_schedule = factories.ScheduleFactory.create(user=user)
        product = factories.ProductFactory.create()
        return Appointment(
            id=deobfuscate_appointment_id(123),
            member_schedule=member_schedule,
            product=product,
            scheduled_start=datetime.datetime.utcnow(),
            scheduled_end=datetime.datetime.utcnow(),
        )
    else:
        return None


@pytest.mark.parametrize(
    "mock_appointment, is_participant, status_code",
    [
        (True, True, 200),  # valid appointment id
        (True, False, 401),  # not a participant
        (False, True, 404),  # appointment not found
    ],
    indirect=["mock_appointment"],
)
def test_post_video_heartbeat_connection(
    mock_appointment,
    is_participant,
    status_code,
    factories,
    client,
    api_helpers,
):
    if mock_appointment and is_participant:
        user = mock_appointment.member
    else:
        user = factories.DefaultUserFactory.create()

    data = {
        "capabilities": ["zoom"],
        "device_type": "web",
    }

    dummy_appt_id = 123
    api_id = mock_appointment.api_id if mock_appointment else dummy_appt_id

    res = client.post(
        f"/api/v1/video/connection/{api_id}/heartbeat",
        data=json.dumps(data),
        headers=api_helpers.json_headers(user),
    )

    assert res.status_code == status_code
