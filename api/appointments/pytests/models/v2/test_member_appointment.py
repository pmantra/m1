from datetime import datetime
from unittest.mock import patch

from appointments.models.v2.member_appointment import MemberAppointmentStruct
from appointments.schemas.appointments import PrivacyType
from models.common import PrivilegeType


@patch("appointments.models.v2.member_appointment.log.error")
def test_member_appointment_bad_video_json(error_log_mock):
    """
    Scenario:
        An appointment's video json string comes back incorrectly formatted from
        the database. Assert that an error log is emitted and that an empty
        VideoStruct is created
    """
    bad_video_struct_str = "incorrectly formatted"
    json_str = """
        {
            "member_disconnected_at": "2024-04-16T03:03:03",
            "practitioner_disconnected_at": "2024-04-16T03:04:03"
        }
    """
    ma = MemberAppointmentStruct(
        id=0,
        schedule_event_id=0,
        member_schedule_id=0,
        product_id=0,
        client_notes="str",
        cancelled_at=datetime.utcnow(),
        scheduled_start=datetime.utcnow(),
        scheduled_end=datetime.utcnow(),
        privacy=PrivacyType.ANONYMOUS,
        privilege_type=PrivilegeType.STANDARD,
        member_started_at=datetime.utcnow(),
        member_ended_at=datetime.utcnow(),
        practitioner_started_at=datetime.utcnow(),
        practitioner_ended_at=datetime.utcnow(),
        disputed_at=datetime.utcnow(),
        video=bad_video_struct_str,
        plan_segment_id=0,
        phone_call_at=None,
        json_str=json_str,
    )

    assert ma.video.session_id is None
    assert ma.video.member_token is None
    assert ma.video.practitioner_token is None

    error_log_mock.assert_called_once()
