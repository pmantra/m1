from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from appointments.services.common import (
    deobfuscate_appointment_id,
    obfuscate_appointment_id,
)
from pytests.db_util import enable_db_performance_warnings
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def setup_three_appointments(
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    appointments = [
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="test purpose",
            scheduled_start=datetime.utcnow(),
        ),
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="test purpose",
            scheduled_start=datetime.utcnow() + timedelta(minutes=60),
        ),
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="test purpose",
            scheduled_start=datetime.utcnow() + timedelta(minutes=120),
        ),
    ]

    return provider, member, appointments


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointment_by_id(
    db,
    client,
    api_helpers,
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    now = datetime.utcnow().replace(microsecond=0)
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)

    appointment = valid_appointment_with_user(
        practitioner=provider,
        member_schedule=member.schedule,
        purpose="test purpose",
        scheduled_start=now + timedelta(minutes=10),
    )

    obfuscated_appt_id = obfuscate_appointment_id(appointment.id)
    with enable_db_performance_warnings(
        database=db,
        # warning_threshold=1,  # uncomment to view all queries being made
        failure_threshold=23,
    ):
        res = client.get(
            f"/api/v2/member/appointments/{obfuscated_appt_id}",
            headers=api_helpers.json_headers(member),
        )
    assert res.status_code == 200
    data = res.json
    assert data["id"] == deobfuscate_appointment_id(appointment.id)
    assert data["product_id"] == appointment.product_id
    assert data["provider"]["id"] == appointment.practitioner_id
    assert data["scheduled_start"] == appointment.scheduled_start.isoformat()
    assert data["scheduled_end"] == appointment.scheduled_end.isoformat()


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list(
    db,
    client,
    api_helpers,
    setup_three_appointments,
):
    now = datetime.utcnow()
    provider, member, appointments = setup_three_appointments
    expected_ids = {a.id for a in appointments}

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=23,
    ):
        query_str = {
            "scheduled_start": now.isoformat(),
            "scheduled_end": (now + timedelta(hours=3)).isoformat(),
            "order_direction": "asc",
        }
        res = client.get(
            "/api/v2/member/appointments",
            headers=api_helpers.json_headers(member),
            query_string=query_str,
        )

    assert res.status_code == 200
    data = res.json["data"]
    actual_ids = {deobfuscate_appointment_id(a.get("id")) for a in data}

    assert actual_ids == expected_ids
