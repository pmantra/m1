from copy import deepcopy
from datetime import datetime
from time import sleep

from freezegun import freeze_time

from pytests.db_util import enable_db_performance_warnings
from utils.flag_groups import APPOINTMENT_ALLOW_RX_OVERWRITE


def test_patch_appointments(
    client,
    db,
    factories,
    api_helpers,
    enterprise_user,
):
    """
    Tests a basic PATCH request to api/v1/appointments

    Additionally sets a base amount of database calls using `enable_db_performance_warnings`
    """
    now = datetime.utcnow()
    member = enterprise_user

    note_str = "test note :)"
    need = factories.NeedFactory.create()
    appt = factories.AppointmentFactory.create(
        scheduled_start=now,
        member_schedule=factories.ScheduleFactory.create(user=member),
    )

    data = {
        "need_id": need.id,
        "notes": note_str,
    }
    with freeze_time("2024-01-01"):
        with enable_db_performance_warnings(
            database=db,
            failure_threshold=12,
            # https://dev.mysql.com/doc/refman/5.7/en/table-scan-avoidance.html
            # The table is so small that it is faster to perform a table scan than to bother with a key lookup.
            # This is common for tables with fewer than 10 rows and a short row length
            query_analyzers=(),
        ):
            res = client.patch(
                f"/api/v1/appointments/{appt.api_id}",
                headers=api_helpers.json_headers(user=member),
                json=data,
            )

        assert res.status_code == 200
        db.session.refresh(appt)
        assert appt.need.id == need.id
        assert appt.client_notes == note_str
        assert appt.modified_at == datetime.utcnow()


def test_patch_appointments_invalid_appointment_id(
    client,
    api_helpers,
    enterprise_user,
):
    """
    Tests that a 404 is returned when an invalid appointment_id is sent
    """
    invalid_appt_id = 4

    res = client.patch(
        f"/api/v1/appointments/{invalid_appt_id}",
        headers=api_helpers.json_headers(user=enterprise_user),
        json={},
    )

    assert res.status_code == 404


def test_patch_appointments_remove_need_when_none(
    client,
    factories,
    api_helpers,
    enterprise_user,
):
    """
    Tests that a need is removed from the appointment when
    it is set to None
    """
    now = datetime.utcnow()
    member = enterprise_user

    need = factories.NeedFactory.create()
    appt = factories.AppointmentFactory.create(
        scheduled_start=now,
        member_schedule=factories.ScheduleFactory.create(user=member),
        need=need,
    )

    res = client.patch(
        f"/api/v1/appointments/{appt.api_id}",
        headers=api_helpers.json_headers(user=member),
        json={"need_id": None},
    )

    assert res.status_code == 200
    assert appt.need is None


def test_patch_appointments_invalid_need_id(
    client,
    factories,
    api_helpers,
    enterprise_user,
):
    """
    Tests that a 404 is returned when an invalid need_id is sent
    """
    now = datetime.utcnow()
    member = enterprise_user

    invalid_need_id = 3
    appt = factories.AppointmentFactory.create(
        scheduled_start=now,
        member_schedule=factories.ScheduleFactory.create(user=member),
    )

    res = client.patch(
        f"/api/v1/appointments/{appt.api_id}",
        headers=api_helpers.json_headers(user=member),
        json={"need_id": invalid_need_id},
    )

    assert res.status_code == 404


def test_patch_appointments_edit_need_id(
    client,
    db,
    factories,
    api_helpers,
    enterprise_user,
):
    """
    Tests that editing an appointment's need works correctly
    when one already exists
    """
    now = datetime.utcnow()
    member = enterprise_user

    note_str = "test note :)"
    old_need = factories.NeedFactory.create()
    expected_need = factories.NeedFactory.create()
    appt = factories.AppointmentFactory.create(
        scheduled_start=now,
        member_schedule=factories.ScheduleFactory.create(user=member),
        need=old_need,
    )

    data = {
        "need_id": expected_need.id,
        "notes": note_str,
    }
    res = client.patch(
        f"/api/v1/appointments/{appt.api_id}",
        headers=api_helpers.json_headers(user=member),
        json=data,
    )

    assert res.status_code == 200
    db.session.refresh(appt)
    assert appt.need.id == expected_need.id
    assert appt.client_notes == note_str


def test_patch_appointments_rx_written_at(
    client,
    db,
    factories,
    api_helpers,
    enterprise_user,
    datetime_now_iso_format,
    datetime_one_hour_later_iso_format,
    ff_test_data,
):
    """
    Tests a PATCH request with rx_written_at and rx_written_via to api/v1/appointments
    """
    ff_test_data.update(
        ff_test_data.flag(APPOINTMENT_ALLOW_RX_OVERWRITE).value_for_all(True)
    )

    now = datetime.utcnow()
    member = enterprise_user
    appt = factories.AppointmentFactory.create(
        scheduled_start=now,
        member_schedule=factories.ScheduleFactory.create(user=member),
        json={"some_field": "some value"},
    )
    data = {
        "rx_written_at": datetime_now_iso_format,
        "rx_written_via": "dosespot",
    }

    res = client.patch(
        f"/api/v1/appointments/{appt.api_id}",
        headers=api_helpers.json_headers(user=appt.practitioner),
        json=data,
    )

    assert res.status_code == 200
    db.session.refresh(appt)
    assert appt.json == {"some_field": "some value", "rx_written_via": "dosespot"}
    assert appt.rx_written_at is not None
    existing_rx_written_at = deepcopy(appt.rx_written_at)

    # The PATCH appointment endpoint ignores rx_written_at in the request and sets the value to datetime.utcnow().
    # Without sleeping for 1 second, the test might run too fast, resulting in the second PATCH call setting
    # rx_written_at to the same value as the first PATCH call. Then assertion that the second rx_written_at >
    # first rx_written_at would fail.
    sleep(1)
    updated_data = {
        "rx_written_at": datetime_one_hour_later_iso_format,
        "rx_written_via": "call",
    }
    res = client.patch(
        f"/api/v1/appointments/{appt.api_id}",
        headers=api_helpers.json_headers(user=appt.practitioner),
        json=updated_data,
    )

    assert res.status_code == 200
    db.session.refresh(appt)
    assert appt.json == {"some_field": "some value", "rx_written_via": "call"}
    assert appt.rx_written_at is not None
    assert appt.rx_written_at > existing_rx_written_at


def test_patch_appointments_rx_written_at_from_member_no_update(
    client,
    db,
    factories,
    api_helpers,
    enterprise_user,
    datetime_now_iso_format,
):
    """
    Tests a member PATCH request with rx_written_at and rx_written_via to api/v1/appointments:
    it won't update these fields in the appointment model.
    """
    now = datetime.utcnow()
    member = enterprise_user
    appt = factories.AppointmentFactory.create(
        scheduled_start=now,
        member_schedule=factories.ScheduleFactory.create(user=member),
        json={"some_field": "some value"},
    )
    data = {
        "rx_written_at": datetime_now_iso_format,
        "rx_written_via": "dosespot",
    }

    res = client.patch(
        f"/api/v1/appointments/{appt.api_id}",
        headers=api_helpers.json_headers(user=member),
        json=data,
    )

    assert res.status_code == 200
    db.session.refresh(appt)
    assert appt.json == {"some_field": "some value"}
    assert appt.rx_written_at is None
