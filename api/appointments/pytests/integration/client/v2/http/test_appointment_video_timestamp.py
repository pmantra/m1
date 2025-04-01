from datetime import datetime, timedelta
from unittest import mock

from freezegun import freeze_time

from appointments.models.constants import APPOINTMENT_STATES
from storage.connection import db


def test_appointment_can_process_member_disconnected_data(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that member disconnected data can be successfully processed.
    """
    appointment = scheduled_appointment
    disconnected_at = (
        (appointment.scheduled_start + timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )

    data = {"disconnected_at": disconnected_at}
    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    assert appointment.member_started_at.isoformat() == disconnected_at
    assert appointment.json.get("member_disconnect_times") == [disconnected_at]


def test_appointment_can_process_provider_disconnected_data(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that provider disconnected data can be successfully processed.
    """
    appointment = scheduled_appointment
    disconnected_at = (
        (appointment.scheduled_start + timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )

    data = {"disconnected_at": disconnected_at}
    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.practitioner),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    assert appointment.practitioner_started_at.isoformat() == disconnected_at
    assert appointment.json.get("practitioner_disconnect_times") == [disconnected_at]


def test_appointment_in_incomplete_state_will_not_process_disconnected_data(
    client,
    api_helpers,
    incomplete_appointment,
):
    """
    Tests that disconnected data will not be processed when appointment is in incomplete state.
    """
    appointment = incomplete_appointment
    disconnected_at = (
        (appointment.scheduled_start + timedelta(minutes=1))
        .replace(microsecond=0)
        .isoformat()
    )

    data = {"disconnected_at": disconnected_at}
    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    assert not appointment.json.get("member_disconnect_times")


def test_video_timestamps_can_process_all_member_fields(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that all member fields can be updated
    """
    appointment = scheduled_appointment
    expected_started_at = (appointment.scheduled_start + timedelta(minutes=10)).replace(
        microsecond=0
    )
    expected_ended_at = (appointment.scheduled_end + timedelta(minutes=10)).replace(
        microsecond=0
    )
    expected_disconnected_at = (
        (appointment.scheduled_start + timedelta(minutes=5))
        .replace(microsecond=0)
        .isoformat()
    )

    data = {
        "started_at": expected_started_at.isoformat(),
        "ended_at": expected_ended_at.isoformat(),
        "disconnected_at": expected_disconnected_at,
    }

    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    assert appointment.member_started_at == expected_started_at
    assert appointment.member_ended_at == expected_ended_at
    assert appointment.json.get("member_disconnect_times") == [expected_disconnected_at]


@freeze_time("2024-01-01")
def test_video_timestamps_modified_at(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that modified_at is advancing correctly
    """
    appointment = scheduled_appointment
    with freeze_time("2024-01-02", tick=False):
        data = {
            "started_at": appointment.scheduled_start.isoformat(),
            "ended_at": appointment.scheduled_end.isoformat(),
        }

        res = client.post(
            f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(appointment.member),
        )
        db.session.refresh(appointment)

        assert res.status_code == 200
        assert appointment.modified_at == datetime.utcnow()


def test_video_timestamps_can_process_phone_call_at(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that the phone_call_at field can be updated
    """
    appointment = scheduled_appointment
    phone_call_at = (appointment.scheduled_start + timedelta(minutes=10)).replace(
        microsecond=0
    )

    data = {
        "phone_call_at": phone_call_at.isoformat(),
    }
    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    assert appointment.phone_call_at == phone_call_at


def test_video_timestamps_can_process_all_provider_fields(
    client,
    api_helpers,
    scheduled_appointment,
):
    """
    Tests that all fields can be updated
    """
    appointment = scheduled_appointment
    expected_started_at = (appointment.scheduled_start + timedelta(minutes=10)).replace(
        microsecond=0
    )
    expected_ended_at = (appointment.scheduled_end + timedelta(minutes=10)).replace(
        microsecond=0
    )
    expected_disconnected_at = (
        (appointment.scheduled_start + timedelta(minutes=5))
        .replace(microsecond=0)
        .isoformat()
    )

    data = {
        "started_at": expected_started_at.isoformat(),
        "ended_at": expected_ended_at.isoformat(),
        "disconnected_at": expected_disconnected_at,
    }
    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.practitioner),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    assert appointment.practitioner_started_at == expected_started_at
    assert appointment.practitioner_ended_at == expected_ended_at
    assert appointment.json.get("practitioner_disconnect_times") == [
        expected_disconnected_at
    ]


def test_video_timestamps_disconnected_at_appends_to_list(
    client,
    api_helpers,
    factories,
):
    """
    Tests that sending "disconnected_at" appends to a list of datetime strings
    """
    first_disconnect_time = datetime.utcnow().replace(microsecond=0).isoformat()
    member_started_at = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=2)
    # SQLalchemy will handle converting the json dict to a str in the DB
    appointment = factories.AppointmentFactory.create(
        scheduled_start=datetime.utcnow() + timedelta(hours=1),
        member_started_at=member_started_at,
        json={"member_disconnect_times": [first_disconnect_time]},
    )

    new_disconnected_at_time = (
        (appointment.scheduled_start + timedelta(minutes=5))
        .replace(microsecond=0)
        .isoformat()
    )
    expected_disconnect_times = {first_disconnect_time, new_disconnected_at_time}

    data = {
        "disconnected_at": new_disconnected_at_time,
    }
    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    # started_at will get set to disconnected at if not set
    assert appointment.member_started_at == member_started_at
    assert appointment.member_ended_at is None
    assert (
        set(appointment.json.get("member_disconnect_times"))
        == expected_disconnect_times
    )


def test_video_timestamps_disconnected_also_sets_started_at(
    client,
    api_helpers,
    factories,
):
    """
    Tests that sending "disconnected_at" also sets member_started_at if it was not set
    previously
    """
    appointment = factories.AppointmentFactory.create(
        scheduled_start=datetime.utcnow() + timedelta(hours=1),
    )
    disconnected_at = (appointment.scheduled_start + timedelta(minutes=1)).replace(
        microsecond=0
    )

    data = {
        "disconnected_at": disconnected_at.isoformat(),
    }
    res = client.post(
        f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(appointment.member),
    )
    db.session.refresh(appointment)

    assert res.status_code == 200
    # started_at will get set to disconnected at if not set
    assert appointment.member_started_at == disconnected_at
    assert appointment.member_ended_at is None
    assert appointment.json.get("member_disconnect_times") == [
        disconnected_at.isoformat()
    ]


def test_video_timestamps__appointment_completion_runs_if_payment_pending_or_resolved(
    client,
    api_helpers,
    factories,
):
    """
    Tests that the appointment completion job runs if the appointment is in the state
    "payment_pending_or_resolved"
    """
    appointment = factories.AppointmentFactory.create(
        scheduled_start=datetime.utcnow() - timedelta(hours=1),
        member_started_at=datetime.utcnow() - timedelta(hours=1),
        practitioner_started_at=datetime.utcnow() - timedelta(hours=1),
        practitioner_ended_at=datetime.utcnow() - timedelta(minutes=1),
    )
    ended_at = (appointment.scheduled_start - timedelta(minutes=1)).replace(
        microsecond=0
    )

    assert appointment.state is APPOINTMENT_STATES.overflowing

    with mock.patch(
        "appointments.services.v2.appointment_timestamp.appointment_completion"
    ) as p:
        mock_delay = mock.MagicMock()
        p.delay = mock_delay

        # We are sending ended_at for the member
        data = {
            "ended_at": ended_at.isoformat(),
        }
        res = client.post(
            f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(appointment.member),
        )

    db.session.refresh(appointment)

    assert res.status_code == 200
    mock_delay.assert_called_once()


def test_video_timestamps__appointment_completion_doesnt_run_if_not_payment_pending_or_resolved(
    client,
    api_helpers,
    factories,
):
    """
    Tests that the appointment completion job does not run if the appointment is in a
    state other than "payment_pending_or_resolved"
    """
    appointment = factories.AppointmentFactory.create(
        scheduled_start=datetime.utcnow() - timedelta(hours=1),
        member_started_at=datetime.utcnow() - timedelta(hours=1),
        practitioner_started_at=datetime.utcnow() - timedelta(hours=1),
        practitioner_ended_at=datetime.utcnow() - timedelta(minutes=1),
    )
    ended_at = (appointment.scheduled_start - timedelta(minutes=1)).replace(
        microsecond=0
    )

    assert appointment.state is APPOINTMENT_STATES.overflowing

    with mock.patch(
        "appointments.services.v2.appointment_timestamp.appointment_completion"
    ) as p:
        mock_delay = mock.MagicMock()
        p.delay = mock_delay

        # We are sending ended_at for the member
        data = {
            "disconnected_at": ended_at.isoformat(),
        }
        res = client.post(
            f"/api/v2/appointments/{appointment.api_id}/video_timestamp",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(appointment.member),
        )

    db.session.refresh(appointment)

    assert res.status_code == 200
    mock_delay.assert_not_called()
